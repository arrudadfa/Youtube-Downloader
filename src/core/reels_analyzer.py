"""Análise de mídia com OpenAI para legendas de Reels do Instagram."""

from __future__ import annotations

import asyncio
import base64
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from src.core.instagram_download import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS
from src.utils.logging import setup_logging

if TYPE_CHECKING:
    from src.utils.config import Settings

logger = setup_logging()

REELS_SYSTEM_PROMPT = """\
Você escreve legendas para Reels do Instagram de um canal dedicado a tecnologia, \
assuntos militares, segredos militares, curiosidades, armamentos e ensaios em voo.

Público-alvo: curiosos, entusiastas de aviação, guerra e ciência.

Regras:
- Conte a história por trás do que aparece na mídia, como quem revela um segredo \
guardado por décadas.
- Use termos técnicos de engenharia, química, aviação e ensaios em voo quando \
couberem naturalmente.
- Tom cavalheiresco e simples, mas convidando a uma reflexão profunda sobre o assunto.
- Escreva em português brasileiro.
- No máximo 4 parágrafos curtos.
- Não use emojis.
- No final, inclua até 3 hashtags relevantes em uma linha separada.
- Baseie-se no que é visível ou inferível; se houver incerteza, indique como \
possibilidade, sem inventar fatos específicos.
"""

USER_PROMPT = (
    "Analise a mídia anexada e escreva a legenda completa para um Reels do Instagram, "
    "seguindo todas as regras do sistema."
)

MAX_VISION_IMAGES = 10


class ReelsAnalysisError(Exception):
    """Erro ao gerar legenda com OpenAI."""


@dataclass
class MediaItem:
    path: Path
    kind: str  # video | photo


class ReelsAnalyzer:
    """Gera legendas para Reels a partir de imagens e vídeos baixados."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: AsyncOpenAI | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openai_api_key)

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._client

    async def analyze_files(self, files: list[tuple[Path, str]]) -> str:
        if not self.enabled:
            raise ReelsAnalysisError("OPENAI_API_KEY não configurada.")

        items = [MediaItem(path=path, kind=kind) for path, kind in files]
        temp_dirs: list[Path] = []
        try:
            image_parts, temp_dirs = await self._build_image_parts(items)
            if not image_parts:
                raise ReelsAnalysisError("Nenhuma imagem extraída para análise.")

            content: list[dict] = [{"type": "text", "text": USER_PROMPT}, *image_parts]
            try:
                response = await self._get_client().chat.completions.create(
                    model=self.settings.openai_model,
                    messages=[
                        {"role": "system", "content": REELS_SYSTEM_PROMPT},
                        {"role": "user", "content": content},
                    ],
                    max_tokens=1200,
                    temperature=0.7,
                )
            except Exception as exc:
                logger.exception("Falha na API OpenAI")
                raise ReelsAnalysisError(f"Erro na OpenAI: {exc}") from exc

            text = (response.choices[0].message.content or "").strip()
            if not text:
                raise ReelsAnalysisError("OpenAI retornou resposta vazia.")
            return text
        finally:
            for temp_dir in temp_dirs:
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def _build_image_parts(self, items: list[MediaItem]) -> tuple[list[dict], list[Path]]:
        parts: list[dict] = []
        temp_dirs: list[Path] = []
        for item in items:
            if len(parts) >= MAX_VISION_IMAGES:
                break
            if item.kind == "photo" or item.path.suffix.lower() in PHOTO_EXTENSIONS:
                parts.append(self._image_part_from_file(item.path))
            elif item.kind == "video" or item.path.suffix.lower() in VIDEO_EXTENSIONS:
                frames, temp_dir = await asyncio.to_thread(self._extract_video_frames, item.path)
                temp_dirs.append(temp_dir)
                for frame in frames:
                    if len(parts) >= MAX_VISION_IMAGES:
                        break
                    parts.append(self._image_part_from_file(frame))
        return parts, temp_dirs

    @staticmethod
    def _image_part_from_file(file_path: Path) -> dict:
        raw = file_path.read_bytes()
        mime = "image/jpeg" if file_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        if file_path.suffix.lower() == ".webp":
            mime = "image/webp"
        encoded = base64.standard_b64encode(raw).decode("ascii")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{encoded}", "detail": "high"},
        }

    def _extract_video_frames(self, video_path: Path, count: int = 3) -> tuple[list[Path], Path]:
        duration = self._video_duration_seconds(video_path)
        if duration <= 0:
            timestamps = [0.0]
        else:
            step = duration / (count + 1)
            timestamps = [step * (index + 1) for index in range(count)]

        temp_dir = Path(tempfile.mkdtemp(prefix="reels_frames_"))
        frames: list[Path] = []
        for index, timestamp in enumerate(timestamps):
            frame_path = temp_dir / f"frame_{index}.jpg"
            cmd = [
                self.settings.ffmpeg_path,
                "-y",
                "-ss",
                str(max(timestamp, 0)),
                "-i",
                str(video_path),
                "-vframes",
                "1",
                "-q:v",
                "2",
                str(frame_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0 and frame_path.exists() and frame_path.stat().st_size > 0:
                frames.append(frame_path)
            else:
                logger.warning(
                    "Falha ao extrair frame %s de %s: %s",
                    index,
                    video_path.name,
                    result.stderr[:200],
                )

        if not frames:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise ReelsAnalysisError(f"Não foi possível extrair frames de {video_path.name}.")
        return frames, temp_dir

    @staticmethod
    def _video_duration_seconds(video_path: Path) -> float:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return 0.0
        try:
            return float(result.stdout.strip())
        except ValueError:
            return 0.0
