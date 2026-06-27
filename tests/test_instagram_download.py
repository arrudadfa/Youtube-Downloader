"""Testes de download Instagram."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.instagram_download import (
    MEDIA_ALBUM,
    MEDIA_PHOTO,
    MEDIA_VIDEO,
    InstagramDownloadError,
    download_instagram_media,
)


class TestDownloadInstagramMedia:
    def test_downloads_video(self, tmp_path: Path) -> None:
        client = MagicMock()
        client.media_pk_from_url.return_value = "123"
        media = MagicMock(media_type=MEDIA_VIDEO)
        client.media_info.return_value = media
        client.video_download.return_value = str(tmp_path / "clip.mp4")
        (tmp_path / "clip.mp4").write_bytes(b"video")

        path, kind = download_instagram_media(client, "https://instagram.com/reel/abc/", str(tmp_path))

        assert kind == "video"
        assert path.name == "clip.mp4"
        client.video_download.assert_called_once_with("123", folder=str(tmp_path))

    def test_downloads_photo(self, tmp_path: Path) -> None:
        client = MagicMock()
        client.media_pk_from_url.return_value = "456"
        media = MagicMock(media_type=MEDIA_PHOTO)
        client.media_info.return_value = media
        client.photo_download.return_value = str(tmp_path / "pic.jpg")
        (tmp_path / "pic.jpg").write_bytes(b"photo")

        path, kind = download_instagram_media(client, "https://instagram.com/p/abc/", str(tmp_path))

        assert kind == "photo"
        assert path.name == "pic.jpg"
        client.photo_download.assert_called_once_with("456", folder=str(tmp_path))

    def test_album_prefers_video(self, tmp_path: Path) -> None:
        client = MagicMock()
        client.media_pk_from_url.return_value = "789"
        media = MagicMock(media_type=MEDIA_ALBUM)
        client.media_info.return_value = media
        photo = tmp_path / "a.jpg"
        video = tmp_path / "b.mp4"
        photo.write_bytes(b"p")
        video.write_bytes(b"v")
        client.album_download.return_value = [str(photo), str(video)]

        path, kind = download_instagram_media(client, "https://instagram.com/p/album/", str(tmp_path))

        assert kind == "video"
        assert path.suffix == ".mp4"

    def test_rate_limit_error(self) -> None:
        from instagrapi.exceptions import PleaseWaitFewMinutes

        client = MagicMock()
        client.media_pk_from_url.side_effect = PleaseWaitFewMinutes("wait")

        with pytest.raises(InstagramDownloadError, match="limitou requisi"):
            download_instagram_media(client, "https://instagram.com/p/x/", "/tmp")
