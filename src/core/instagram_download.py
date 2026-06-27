"""Download de mídia Instagram via instagrapi."""

from __future__ import annotations

from pathlib import Path

from instagrapi import Client
from instagrapi.exceptions import (
    ClientThrottledError,
    FeedbackRequired,
    MediaNotFound,
    PleaseWaitFewMinutes,
    PrivateError,
    RateLimitError,
)

MEDIA_PHOTO = 1
MEDIA_VIDEO = 2
MEDIA_ALBUM = 8

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class InstagramDownloadError(Exception):
    """Erro ao baixar mídia do Instagram."""


def download_instagram_media(client: Client, url: str, folder: str) -> tuple[Path, str]:
    """Baixa foto, vídeo ou item de álbum. Retorna (caminho, 'video'|'photo')."""
    try:
        media_pk = client.media_pk_from_url(url)
        media = client.media_info(media_pk)
    except (PleaseWaitFewMinutes, RateLimitError, ClientThrottledError, FeedbackRequired) as exc:
        raise InstagramDownloadError(
            "Instagram limitou requisições. Aguarde alguns minutos e tente novamente."
        ) from exc
    except MediaNotFound as exc:
        raise InstagramDownloadError("Post não encontrado ou removido.") from exc
    except PrivateError as exc:
        raise InstagramDownloadError("Conteúdo privado ou inacessível.") from exc

    if media.media_type == MEDIA_VIDEO:
        path = client.video_download(media_pk, folder=folder)
        return Path(path), "video"

    if media.media_type == MEDIA_PHOTO:
        path = client.photo_download(media_pk, folder=folder)
        return Path(path), "photo"

    if media.media_type == MEDIA_ALBUM:
        paths = client.album_download(media_pk, folder=folder)
        return _pick_best_album_file(paths)

    raise InstagramDownloadError(
        f"Tipo de mídia Instagram não suportado (type={media.media_type})."
    )


def _pick_best_album_file(paths: list[str | Path]) -> tuple[Path, str]:
    path_objs = [Path(p) for p in paths]
    videos = [p for p in path_objs if p.suffix.lower() in VIDEO_EXTENSIONS]
    if videos:
        best = max(videos, key=lambda p: p.stat().st_mtime)
        return best, "video"

    photos = [p for p in path_objs if p.suffix.lower() in PHOTO_EXTENSIONS]
    if photos:
        best = max(photos, key=lambda p: p.stat().st_mtime)
        return best, "photo"

    raise InstagramDownloadError("Álbum sem foto ou vídeo reconhecível.")
