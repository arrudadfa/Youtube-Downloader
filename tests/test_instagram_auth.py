"""Testes para autenticação Instagram com 2FA."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from instagrapi.exceptions import TwoFactorRequired

from src.core.instagram_auth import InstagramAuthError, InstagramSessionManager
from src.utils.config import Settings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("INSTAGRAM_USERNAME", "user@test")
    monkeypatch.setenv("INSTAGRAM_PASSWORD", "secret")
    monkeypatch.setenv("INSTAGRAM_SESSION_PATH", str(tmp_path / "session.json"))
    return Settings()


class TestVerificationCode:
    def test_uses_env_code(self, settings, monkeypatch):
        monkeypatch.setenv("INSTAGRAM_VERIFICATION_CODE", "654321")
        settings = Settings()
        mgr = InstagramSessionManager(settings)
        assert mgr.get_verification_code() == "654321"

    def test_runtime_code_overrides_env(self, settings, monkeypatch):
        monkeypatch.setenv("INSTAGRAM_VERIFICATION_CODE", "654321")
        settings = Settings()
        mgr = InstagramSessionManager(settings)
        mgr.set_verification_code("111222")
        assert mgr.get_verification_code() == "111222"


class TestLoginFlow:
    def test_login_passes_verification_code(self, settings):
        mgr = InstagramSessionManager(settings)
        mgr.set_verification_code("123456")
        mock_client = MagicMock()

        with patch("src.core.instagram_auth.Client", return_value=mock_client):
            client = mgr._fresh_login(mock_client)

        mock_client.login.assert_called_once_with("user@test", "secret", verification_code="123456")
        mock_client.dump_settings.assert_called_once()
        assert client is mock_client

    def test_two_factor_without_code_raises_helpful_error(self, settings):
        mgr = InstagramSessionManager(settings)
        mock_client = MagicMock()
        mock_client.login.side_effect = TwoFactorRequired("2FA required")

        with pytest.raises(InstagramAuthError, match="/ig2fa"):
            mgr._fresh_login(mock_client)

    def test_loads_existing_session_before_fresh_login(self, settings, tmp_path):
        session_file = Path(settings.instagram_session_path)
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text("{}", encoding="utf-8")

        mgr = InstagramSessionManager(settings)
        mock_client = MagicMock()

        with patch("src.core.instagram_auth.Client", return_value=mock_client):
            client = mgr.get_client()

        mock_client.load_settings.assert_called_once_with(session_file)
        mock_client.login.assert_called_once_with("user@test", "secret", relogin=True)
        assert client is mock_client

    def test_invalid_session_falls_back_to_fresh_login(self, settings, tmp_path):
        session_file = Path(settings.instagram_session_path)
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text("{}", encoding="utf-8")

        mgr = InstagramSessionManager(settings)
        mgr.set_verification_code("999888")
        mock_client = MagicMock()
        mock_client.login.side_effect = [Exception("expired"), None]

        with patch("src.core.instagram_auth.Client", return_value=mock_client):
            client = mgr.get_client()

        assert mock_client.login.call_count == 2
        mock_client.login.assert_any_call("user@test", "secret", relogin=True)
        mock_client.login.assert_any_call("user@test", "secret", verification_code="999888")
        assert client is mock_client
