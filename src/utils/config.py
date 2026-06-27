"""Configuração via variáveis de ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


def _env_bool(key: str, default: bool) -> bool:
    return os.getenv(key, str(default)).lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    owner_user_id: int = field(default_factory=lambda: _env_int("OWNER_USER_ID", 163177765))
    star_price: int = field(default_factory=lambda: _env_int("STAR_PRICE", 1))
    max_video_size_mb: int = field(default_factory=lambda: _env_int("MAX_VIDEO_SIZE_MB", 50))
    download_timeout_seconds: int = field(default_factory=lambda: _env_int("DOWNLOAD_TIMEOUT_SECONDS", 120))
    max_concurrent_downloads: int = field(default_factory=lambda: _env_int("MAX_CONCURRENT_DOWNLOADS", 3))
    storage_type: str = field(default_factory=lambda: os.getenv("STORAGE_TYPE", "local"))
    local_storage_path: Path = field(
        default_factory=lambda: Path(os.getenv("LOCAL_STORAGE_PATH", "./downloads"))
    )
    ffmpeg_path: str = field(default_factory=lambda: os.getenv("FFMPEG_PATH", "ffmpeg"))
    enable_compression: bool = field(default_factory=lambda: _env_bool("ENABLE_COMPRESSION", True))
    instagram_username: str = field(default_factory=lambda: os.getenv("INSTAGRAM_USERNAME", ""))
    instagram_password: str = field(default_factory=lambda: os.getenv("INSTAGRAM_PASSWORD", ""))
    instagram_verification_code: str = field(
        default_factory=lambda: os.getenv("INSTAGRAM_VERIFICATION_CODE", "")
    )
    instagram_session_path: Path = field(
        default_factory=lambda: Path(os.getenv("INSTAGRAM_SESSION_PATH", "./data/instagram_session.json"))
    )
    instagram_cookies_path: Path | None = field(
        default_factory=lambda: (
            Path(p) if (p := os.getenv("INSTAGRAM_COOKIES_PATH", "").strip()) else None
        )
    )
    instagram_cookies_browser: str = field(
        default_factory=lambda: os.getenv("INSTAGRAM_COOKIES_BROWSER", "").strip()
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    bot_mode: str = field(default_factory=lambda: os.getenv("BOT_MODE", "polling"))
    webhook_url: str = field(default_factory=lambda: os.getenv("WEBHOOK_URL", ""))
    webhook_secret: str = field(default_factory=lambda: os.getenv("WEBHOOK_SECRET", ""))
    s3_bucket: str = field(default_factory=lambda: os.getenv("S3_BUCKET", ""))
    s3_region: str = field(default_factory=lambda: os.getenv("S3_REGION", "us-east-1"))
    s3_access_key: str = field(default_factory=lambda: os.getenv("S3_ACCESS_KEY", ""))
    s3_secret_key: str = field(default_factory=lambda: os.getenv("S3_SECRET_KEY", ""))

    def __post_init__(self) -> None:
        if not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN ausente no .env")


def get_settings() -> Settings:
    return Settings()
