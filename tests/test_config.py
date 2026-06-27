"""Testes para config."""

import os

import pytest


def test_settings_load_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.delenv("MAX_VIDEO_SIZE_MB", raising=False)

    from src.utils.config import Settings

    settings = Settings()
    assert settings.max_video_size_mb == 50
    assert settings.download_timeout_seconds == 120
    assert settings.owner_user_id == 163177765
    assert settings.openai_model == "gpt-4o"


def test_settings_requires_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    from src.utils.config import Settings

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        Settings()
