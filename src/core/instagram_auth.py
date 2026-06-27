"""Autenticação Instagram com 2FA e sessão persistente."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired

from src.utils.config import Settings
from src.utils.logging import setup_logging

logger = setup_logging()


class InstagramAuthError(Exception):
    """Erro de login ou sessão Instagram."""


class InstagramSessionManager:
    """Gerencia login Instagram, 2FA e persistência de sessão."""

    _instances: dict[str, InstagramSessionManager] = {}
    _lock = Lock()

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Client | None = None
        self._pending_code: str | None = None

    @classmethod
    def for_settings(cls, settings: Settings) -> InstagramSessionManager:
        key = f"{settings.instagram_username}:{settings.instagram_session_path}"
        with cls._lock:
            if key not in cls._instances:
                cls._instances[key] = cls(settings)
            return cls._instances[key]

    @property
    def session_path(self) -> Path:
        return Path(self.settings.instagram_session_path)

    def set_verification_code(self, code: str) -> None:
        self._pending_code = code.strip()
        self._client = None

    def get_verification_code(self) -> str:
        if self._pending_code:
            return self._pending_code
        return (self.settings.instagram_verification_code or "").strip()

    def get_client(self) -> Client:
        """Login ou restauração de sessão. Levanta InstagramAuthError se 2FA faltar."""
        return self.authenticate()

    def authenticate(self) -> Client:
        if self._client is not None:
            return self._client

        client = Client()
        if self.session_path.exists():
            try:
                client.load_settings(self.session_path)
                client.login(
                    self.settings.instagram_username,
                    self.settings.instagram_password,
                    relogin=True,
                )
                self._client = client
                logger.info("Sessão Instagram restaurada: %s", self.session_path)
                return client
            except Exception as exc:
                logger.warning("Sessão Instagram expirada, novo login: %s", exc)

        self._client = self._fresh_login(client)
        return self._client

    def _fresh_login(self, client: Client) -> Client:
        code = self.get_verification_code()
        try:
            client.login(
                self.settings.instagram_username,
                self.settings.instagram_password,
                verification_code=code,
            )
        except TwoFactorRequired as exc:
            raise InstagramAuthError(
                "Instagram requer 2FA. Defina INSTAGRAM_VERIFICATION_CODE no .env "
                "ou envie /ig2fa <código TOTP de 6 dígitos>."
            ) from exc

        self._persist_session(client)
        self._pending_code = None
        logger.info("Login Instagram concluído para %s", self.settings.instagram_username)
        return client

    def _persist_session(self, client: Client) -> None:
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        client.dump_settings(self.session_path)
        logger.info("Sessão Instagram salva em %s", self.session_path)

    def invalidate(self) -> None:
        self._client = None
        self._pending_code = None
