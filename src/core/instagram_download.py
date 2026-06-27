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


def download_instagram_media(
    client: Client, url: str, folder: str
) -> list[tuple[Path, str]]:
    """Baixa foto, vídeo ou carrossel. Retorna lista de (caminho, 'video'|'photo')."""
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
        return [(Path(path), "video")]

    if media.media_type == MEDIA_PHOTO:
        path = client.photo_download(media_pk, folder=folder)
        return [(Path(path), "photo")]

    if media.media_type == MEDIA_ALBUM:
        paths = client.album_download(media_pk, folder=folder)
        return _collect_album_files(paths)

    raise InstagramDownloadError(
        f"Tipo de mídia Instagram não suportado (type={media.media_type})."
    )


def _collect_album_files(paths: list[str | Path]) -> list[tuple[Path, str]]:
    """Retorna todas as mídias do carrossel na ordem do download."""
    result: list[tuple[Path, str]] = []
    for raw in paths:
        path = Path(raw)
        ext = path.suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            result.append((path, "video"))
        elif ext in PHOTO_EXTENSIONS:
            result.append((path, "photo"))
    if not result:
        raise InstagramDownloadError("Álbum sem foto ou vídeo reconhecível.")
    return result
