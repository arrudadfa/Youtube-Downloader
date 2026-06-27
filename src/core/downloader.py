"""Orquestrador principal de downloads."""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from src.core.instagram_auth import InstagramAuthError, InstagramSessionManager
from src.core.instagram_cookies import resolve_gallery_cookies_path, session_has_login
from src.core.instagram_download import (
    InstagramDownloadError,
    PHOTO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    download_instagram_media,
)
from src.core.platforms import Platform, detect_platform, get_download_strategy
from src.utils.config import Settings
from src.utils.logging import setup_logging

logger = setup_logging()


async def _maybe_await(value: object) -> None:
    if asyncio.iscoroutine(value):
        await value


class DownloadError(Exception):
    """Erro durante download ou pós-processamento."""


@dataclass
class DownloadResult:
    file_path: Path
    title: str
    platform: str
    size_bytes: int
    media_kind: str = "video"


class VideoDownloader:
    """Coordena download por plataforma com fallback e compressão."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
        self._output_dir = settings.local_storage_path
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._instagram = InstagramSessionManager.for_settings(settings)

    async def download(
        self,
        url: str,
        progress_callback: Optional[Callable[[str], "asyncio.Future | None"]] = None,
    ) -> DownloadResult:
        platform = detect_platform(url)
        if platform is None:
            raise DownloadError("Plataforma não suportada.")

        async with self._semaphore:
            return await asyncio.wait_for(
                self._download_with_fallback(url, platform, progress_callback),
                timeout=self.settings.download_timeout_seconds,
            )

    async def _download_with_fallback(
        self,
        url: str,
        platform: Platform,
        progress_callback: Optional[Callable[[str], None]],
    ) -> DownloadResult:
        strategy = get_download_strategy(platform)
        tools = self._tools_for_platform(platform, strategy)
        last_error: Exception | None = None
        media_kind = "video"

        for tool in tools:
            try:
                if progress_callback:
                    await _maybe_await(progress_callback(f"Baixando via {tool}..."))
                logger.info("Tentativa %s para %s (%s)", tool, url, platform.value)
                file_path, tool_media_kind = await self._run_tool(tool, url, platform)
                media_kind = tool_media_kind
                file_path = await self._ensure_size_limit(
                    file_path, progress_callback, media_kind=media_kind
                )
                size = file_path.stat().st_size
                title = file_path.stem
                return DownloadResult(
                    file_path=file_path,
                    title=title,
                    platform=platform.value,
                    size_bytes=size,
                    media_kind=media_kind,
                )
            except Exception as exc:
                last_error = exc
                logger.warning("Falha com %s: %s", tool, exc)
                if platform == Platform.INSTAGRAM and self._should_abort_instagram_fallback(exc):
                    raise DownloadError(self._friendly_error(exc))

        raise DownloadError(self._friendly_error(last_error))

    def _tools_for_platform(self, platform: Platform, strategy) -> tuple[str, ...]:
        tools = (strategy.primary, *strategy.fallbacks)
        if platform != Platform.INSTAGRAM:
            return tools
        if self._instagram_gallery_cookies_available():
            return tools
        if self.settings.instagram_username and self.settings.instagram_password:
            return (strategy.primary,)
        return tools

    def _instagram_gallery_cookies_available(self) -> bool:
        if self.settings.instagram_cookies_browser:
            return True
        if self.settings.instagram_cookies_path and self.settings.instagram_cookies_path.exists():
            return True
        return session_has_login(self.settings.instagram_session_path)

    def _gallery_cookies_cache_path(self) -> Path:
        return self.settings.instagram_session_path.parent / "instagram_gallery_cookies.txt"

    def _resolve_instagram_cookies_path(self) -> Path | None:
        return resolve_gallery_cookies_path(
            self.settings.instagram_session_path,
            self.settings.instagram_cookies_path,
            self._gallery_cookies_cache_path(),
        )

    def _gallery_dl_cookie_args(self, platform: Platform) -> list[str]:
        if platform != Platform.INSTAGRAM:
            return []
        if self.settings.instagram_cookies_browser:
            return ["--cookies-from-browser", self.settings.instagram_cookies_browser]
        cookies_path = self._resolve_instagram_cookies_path()
        if cookies_path:
            logger.info("gallery-dl usando cookies: %s", cookies_path)
            return ["-C", str(cookies_path)]
        return []

    async def _run_tool(self, tool: str, url: str, platform: Platform) -> tuple[Path, str]:
        if tool == "yt-dlp":
            return await self._download_ytdlp(url), "video"
        if tool == "gallery-dl":
            return await self._download_gallery_dl(url, platform)
        if tool == "instagrapi":
            return await self._download_instagrapi(url)
        raise DownloadError(f"Ferramenta desconhecida: {tool}")

    async def _download_ytdlp(self, url: str) -> Path:
        """YouTube, X, TikTok (fallback)."""
        out_template = str(self._output_dir / "%(id)s.%(ext)s")
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-f",
            "best[ext=mp4]/best",
            "--merge-output-format",
            "mp4",
            "-o",
            out_template,
            url,
        ]
        await self._run_subprocess(cmd)
        return self._find_latest_file()

    async def _download_gallery_dl(self, url: str, platform: Platform) -> tuple[Path, str]:
        """Instagram, TikTok, Threads."""
        dest = self._output_dir / hashlib.md5(url.encode()).hexdigest()[:12]
        dest.mkdir(parents=True, exist_ok=True)
        cmd = ["gallery-dl", "-d", str(dest), *self._gallery_dl_cookie_args(platform), url]
        await self._run_subprocess(cmd)
        file_path = self._find_latest_file(search_dir=dest, allow_photos=True)
        return file_path, self._media_kind_from_path(file_path)

    async def _download_instagrapi(self, url: str) -> tuple[Path, str]:
        """Instagram via instagrapi (requer credenciais + 2FA na 1ª vez)."""
        if not self.settings.instagram_username or not self.settings.instagram_password:
            raise DownloadError("Credenciais Instagram não configuradas.")

        def _sync_download() -> tuple[Path, str]:
            try:
                client = self._instagram.get_client()
            except InstagramAuthError as exc:
                raise DownloadError(str(exc)) from exc
            self._refresh_gallery_cookies_from_client(client)
            try:
                return download_instagram_media(client, url, str(self._output_dir))
            except InstagramDownloadError as exc:
                raise DownloadError(str(exc)) from exc

        return await asyncio.to_thread(_sync_download)

    def _refresh_gallery_cookies_from_client(self, client) -> None:
        from src.core.instagram_cookies import export_cookies_from_client

        cache_path = self._gallery_cookies_cache_path()
        if export_cookies_from_client(client, cache_path):
            logger.info("Cookies gallery-dl atualizados: %s", cache_path)

    async def _run_subprocess(self, cmd: list[str]) -> None:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_text = stderr.decode(errors="replace").lower()
            if "429" in err_text or "rate" in err_text:
                raise DownloadError("Limite de requisições (429). Tente mais tarde.")
            if "private" in err_text or "login" in err_text:
                raise DownloadError("Conteúdo privado ou requer autenticação.")
            raise DownloadError(stderr.decode(errors="replace")[:500])

    def _find_latest_file(self, search_dir: Path | None = None, allow_photos: bool = False) -> Path:
        base = search_dir or self._output_dir
        extensions = VIDEO_EXTENSIONS | PHOTO_EXTENSIONS if allow_photos else VIDEO_EXTENSIONS
        candidates = [
            p
            for p in base.rglob("*")
            if p.is_file() and p.suffix.lower() in extensions
        ]
        if not candidates:
            kind = "mídia" if allow_photos else "vídeo"
            raise DownloadError(f"Nenhum arquivo de {kind} encontrado após download.")
        return max(candidates, key=lambda p: p.stat().st_mtime)

    @staticmethod
    def _media_kind_from_path(file_path: Path) -> str:
        if file_path.suffix.lower() in PHOTO_EXTENSIONS:
            return "photo"
        return "video"

    async def _ensure_size_limit(
        self,
        file_path: Path,
        progress_callback: Optional[Callable[[str], None]],
        media_kind: str = "video",
    ) -> Path:
        max_bytes = self.settings.max_video_size_mb * 1024 * 1024
        if media_kind == "photo":
            if file_path.stat().st_size <= max_bytes:
                return file_path
            raise DownloadError(
                f"Imagem excede {self.settings.max_video_size_mb}MB."
            )
        if file_path.stat().st_size <= max_bytes:
            return file_path
        if not self.settings.enable_compression:
            raise DownloadError(
                f"Arquivo excede {self.settings.max_video_size_mb}MB e compressão está desabilitada."
            )
        if progress_callback:
            await _maybe_await(progress_callback("Comprimindo vídeo para caber no Telegram..."))
        return await self._compress_video(file_path, max_bytes)

    async def _compress_video(self, file_path: Path, max_bytes: int) -> Path:
        output = file_path.with_name(f"{file_path.stem}_compressed.mp4")
        crf = 28
        for attempt in range(3):
            cmd = [
                self.settings.ffmpeg_path,
                "-y",
                "-i",
                str(file_path),
                "-c:v",
                "libx264",
                "-crf",
                str(crf),
                "-preset",
                "fast",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                str(output),
            ]
            await self._run_subprocess(cmd)
            if output.stat().st_size <= max_bytes:
                if output != file_path:
                    file_path.unlink(missing_ok=True)
                return output
            crf += 4
            output.unlink(missing_ok=True)

        raise DownloadError(
            f"Não foi possível comprimir abaixo de {self.settings.max_video_size_mb}MB."
        )

    @staticmethod
    def _should_abort_instagram_fallback(exc: Exception) -> bool:
        if isinstance(exc, InstagramAuthError):
            return True
        if isinstance(exc, DownloadError):
            msg = str(exc).lower()
            if "2fa" in msg or "autentica" in msg or "credenciais instagram" in msg:
                return True
            if "limitou requisi" in msg or "429" in msg:
                return True
        return False

    @staticmethod
    def _friendly_error(exc: Exception | None) -> str:
        if exc is None:
            return "Falha desconhecida no download."
        if isinstance(exc, asyncio.TimeoutError):
            return "Timeout: download excedeu o tempo limite."
        if isinstance(exc, DownloadError):
            return str(exc)
        return f"Erro no download: {exc}"

    def cleanup(self, file_path: Path) -> None:
        try:
            if file_path.exists():
                file_path.unlink()
            parent = file_path.parent
            if parent != self._output_dir and parent.exists() and not any(parent.iterdir()):
                shutil.rmtree(parent, ignore_errors=True)
        except OSError as exc:
            logger.warning("Falha ao limpar %s: %s", file_path, exc)
