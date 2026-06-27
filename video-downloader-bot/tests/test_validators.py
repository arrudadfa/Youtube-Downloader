"""Testes para validação de URLs."""

import pytest

from src.core.validators import extract_url, is_supported_url, validate_url


class TestValidateUrl:
    def test_youtube_watch_url(self):
        result = validate_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.is_valid
        assert result.platform == "youtube"

    def test_youtube_short_url(self):
        result = validate_url("https://youtu.be/dQw4w9WgXcQ")
        assert result.is_valid
        assert result.platform == "youtube"

    def test_instagram_reel(self):
        result = validate_url("https://www.instagram.com/reel/ABC123/")
        assert result.is_valid
        assert result.platform == "instagram"

    def test_tiktok_url(self):
        result = validate_url("https://www.tiktok.com/@user/video/1234567890")
        assert result.is_valid
        assert result.platform == "tiktok"

    def test_x_twitter_url(self):
        result = validate_url("https://x.com/user/status/1234567890")
        assert result.is_valid
        assert result.platform == "x"

    def test_threads_url(self):
        result = validate_url("https://www.threads.net/@user/post/ABC123")
        assert result.is_valid
        assert result.platform == "threads"

    def test_unsupported_url(self):
        result = validate_url("https://example.com/video")
        assert not result.is_valid
        assert result.platform is None

    def test_invalid_scheme(self):
        result = validate_url("ftp://youtube.com/watch?v=abc")
        assert not result.is_valid


class TestExtractUrl:
    def test_extract_from_message_with_text(self):
        url = extract_url("Olha esse vídeo https://youtu.be/abc123 legal né?")
        assert url == "https://youtu.be/abc123"

    def test_extract_none_when_no_url(self):
        assert extract_url("sem link aqui") is None


class TestIsSupportedUrl:
    def test_supported_returns_true(self):
        assert is_supported_url("https://youtube.com/watch?v=abc")

    def test_unsupported_returns_false(self):
        assert not is_supported_url("https://vimeo.com/123")
