"""Testes para reels_analyzer."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.reels_analyzer import ReelsAnalyzer, ReelsAnalysisError


@pytest.fixture
def settings_with_openai(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from src.utils.config import Settings

    return Settings()


@pytest.fixture
def settings_without_openai(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from src.utils.config import Settings

    return Settings()


class TestReelsAnalyzer:
    def test_disabled_without_api_key(self, settings_without_openai):
        analyzer = ReelsAnalyzer(settings_without_openai)
        assert analyzer.enabled is False

    def test_enabled_with_api_key(self, settings_with_openai):
        analyzer = ReelsAnalyzer(settings_with_openai)
        assert analyzer.enabled is True

    @pytest.mark.asyncio
    async def test_analyze_requires_api_key(self, settings_without_openai, tmp_path):
        analyzer = ReelsAnalyzer(settings_without_openai)
        image = tmp_path / "photo.jpg"
        image.write_bytes(b"fake")

        with pytest.raises(ReelsAnalysisError, match="OPENAI_API_KEY"):
            await analyzer.analyze_files([(image, "photo")])

    @pytest.mark.asyncio
    async def test_analyze_photo_success(self, settings_with_openai, tmp_path):
        analyzer = ReelsAnalyzer(settings_with_openai)
        image = tmp_path / "photo.jpg"
        image.write_bytes(b"fake-jpeg-bytes")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Legenda de teste.\n\n#aviação"))]
        mock_create = AsyncMock(return_value=mock_response)

        with patch.object(analyzer, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create = mock_create
            result = await analyzer.analyze_files([(image, "photo")])

        assert "Legenda de teste" in result
        mock_create.assert_awaited_once()
        call_kwargs = mock_create.await_args.kwargs
        assert call_kwargs["model"] == settings_with_openai.openai_model
        user_content = call_kwargs["messages"][1]["content"]
        assert user_content[0]["type"] == "text"
        assert user_content[1]["type"] == "image_url"

    @pytest.mark.asyncio
    async def test_analyze_video_extracts_frames(self, settings_with_openai, tmp_path):
        analyzer = ReelsAnalyzer(settings_with_openai)
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"fake-video")

        frame = tmp_path / "frame_0.jpg"
        frame.write_bytes(b"frame-bytes")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Legenda do vídeo."))]
        mock_create = AsyncMock(return_value=mock_response)

        with (
            patch.object(analyzer, "_extract_video_frames", return_value=([frame], tmp_path)),
            patch.object(analyzer, "_get_client") as mock_client,
        ):
            mock_client.return_value.chat.completions.create = mock_create
            result = await analyzer.analyze_files([(video, "video")])

        assert result == "Legenda do vídeo."
        assert mock_create.await_args.kwargs["messages"][1]["content"][1]["type"] == "image_url"
