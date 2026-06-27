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
        tools = (strategy.primary, *strategy.fallbacks)
        last_error: Exception | None = None

        for tool in tools:
            try:
                if progress_callback:
                    await _maybe_await(progress_callback(f"Baixando via {tool}..."))
                logger.info("Tentativa %s para %s (%s)", tool, url, platform.value)
                file_path = await self._run_tool(tool, url, platform)
                file_path = await self._ensure_size_limit(file_path, progress_callback)
                size = file_path.stat().st_size
                title = file_path.stem
                return DownloadResult(
                    file_path=file_path,
                    title=title,
                    platform=platform.value,
                    size_bytes=size,
                )
            except Exception as exc:
                last_error = exc
                logger.warning("Falha com %s: %s", tool, exc)

        raise DownloadError(self._friendly_error(last_error))

    async def _run_tool(self, tool: str, url: str, platform: Platform) -> Path:
        if tool == "yt-dlp":
            return await self._download_ytdlp(url)
        if tool == "gallery-dl":
            return await self._download_gallery_dl(url)
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

    async def _download_gallery_dl(self, url: str) -> Path:
        """Instagram, TikTok, Threads."""
        dest = self._output_dir / hashlib.md5(url.encode()).hexdigest()[:12]
        dest.mkdir(parents=True, exist_ok=True)
        cmd = ["gallery-dl", "-d", str(dest), url]
        await self._run_subprocess(cmd)
        return self._find_latest_file(search_dir=dest)

    async def _download_instagrapi(self, url: str) -> Path:
        """Instagram via instagrapi (requer credenciais + 2FA na 1ª vez)."""
        if not self.settings.instagram_username or not self.settings.instagram_password:
            raise DownloadError("Credenciais Instagram não configuradas.")

        def _sync_download() -> Path:
            try:
                client = self._instagram.get_client()
            except InstagramAuthError as exc:
                raise DownloadError(str(exc)) from exc
            media_pk = client.media_pk_from_url(url)
            path = client.video_download(media_pk, folder=str(self._output_dir))
            return Path(path)

        return await asyncio.to_thread(_sync_download)

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

    def _find_latest_file(self, search_dir: Path | None = None) -> Path:
        base = search_dir or self._output_dir
        candidates = [
            p
            for p in base.rglob("*")
            if p.is_file() and p.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}
        ]
        if not candidates:
            raise DownloadError("Nenhum arquivo de vídeo encontrado após download.")
        return max(candidates, key=lambda p: p.stat().st_mtime)

    async def _ensure_size_limit(
        self,
        file_path: Path,
        progress_callback: Optional[Callable[[str], None]],
    ) -> Path:
        max_bytes = self.settings.max_video_size_mb * 1024 * 1024
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
