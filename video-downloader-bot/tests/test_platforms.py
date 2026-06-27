"""Testes para detecção de plataforma."""

import pytest

from src.core.platforms import Platform, detect_platform, get_download_strategy


class TestDetectPlatform:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.youtube.com/watch?v=abc", Platform.YOUTUBE),
            ("https://youtu.be/abc", Platform.YOUTUBE),
            ("https://youtube.com/shorts/abc", Platform.YOUTUBE),
            ("https://www.instagram.com/reel/xyz/", Platform.INSTAGRAM),
            ("https://instagram.com/p/xyz/", Platform.INSTAGRAM),
            ("https://www.tiktok.com/@u/video/1", Platform.TIKTOK),
            ("https://vm.tiktok.com/abc/", Platform.TIKTOK),
            ("https://x.com/user/status/1", Platform.X),
            ("https://twitter.com/user/status/1", Platform.X),
            ("https://www.threads.net/@u/post/abc", Platform.THREADS),
        ],
    )
    def test_detects_platform(self, url, expected):
        assert detect_platform(url) == expected

    def test_unknown_returns_none(self):
        assert detect_platform("https://example.com") is None


class TestGetDownloadStrategy:
    def test_youtube_uses_ytdlp(self):
        strategy = get_download_strategy(Platform.YOUTUBE)
        assert strategy.primary == "yt-dlp"

    def test_instagram_uses_instagrapi_primary(self):
        strategy = get_download_strategy(Platform.INSTAGRAM)
        assert strategy.primary == "instagrapi"
        assert "gallery-dl" in strategy.fallbacks

    def test_tiktok_uses_gallery_dl_primary(self):
        strategy = get_download_strategy(Platform.TIKTOK)
        assert strategy.primary == "gallery-dl"
        assert "yt-dlp" in strategy.fallbacks

    def test_threads_uses_gallery_dl(self):
        strategy = get_download_strategy(Platform.THREADS)
        assert strategy.primary == "gallery-dl"
