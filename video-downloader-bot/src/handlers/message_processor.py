"""Processamento de mensagens e controle de acesso."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from src.core.validators import ValidationResult, extract_url, validate_url
from src.utils.config import Settings


@dataclass
class ProcessResult:
    action: str  # download | invoice | error | ignore
    url: Optional[str] = None
    platform: Optional[str] = None
    message: Optional[str] = None
    payload: Optional[str] = None


def is_owner(user_id: int, settings: Settings | None = None) -> bool:
    owner_id = settings.owner_user_id if settings else 163177765
    return user_id == owner_id


def should_charge_star(user_id: int, settings: Settings | None = None) -> bool:
    return not is_owner(user_id, settings)


def build_invoice_payload(url: str, user_id: int) -> str:
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"dl:{user_id}:{url_hash}"


def parse_invoice_payload(payload: str) -> tuple[int, str] | None:
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != "dl":
        return None
    return int(parts[1]), parts[2]


class MessageProcessor:
    """Interpreta mensagens e decide o fluxo (download direto ou pagamento)."""

    SUPPORTED_MSG = (
        "Plataformas suportadas:\n"
        "• YouTube (youtube.com, youtu.be)\n"
        "• Instagram (instagram.com)\n"
        "• TikTok (tiktok.com)\n"
        "• X / Twitter (x.com, twitter.com)\n"
        "• Threads (threads.net)\n\n"
        "Envie a URL do vídeo."
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pending_urls: dict[str, str] = {}

    def register_pending_url(self, payload: str, url: str) -> None:
        self._pending_urls[payload] = url

    def pop_pending_url(self, payload: str) -> Optional[str]:
        return self._pending_urls.pop(payload, None)

    def process_text(self, text: str, user_id: int) -> ProcessResult:
        if not text or not text.strip():
            return ProcessResult(action="ignore")

        url = extract_url(text)
        if not url:
            if text.startswith("/"):
                return ProcessResult(action="ignore")
            return ProcessResult(action="error", message=self.SUPPORTED_MSG)

        validation: ValidationResult = validate_url(url)
        if not validation.is_valid:
            return ProcessResult(
                action="error",
                message=validation.error or self.SUPPORTED_MSG,
            )

        if should_charge_star(user_id, self.settings):
            payload = build_invoice_payload(url, user_id)
            self.register_pending_url(payload, url)
            return ProcessResult(
                action="invoice",
                url=url,
                platform=validation.platform,
                payload=payload,
            )

        return ProcessResult(
            action="download",
            url=url,
            platform=validation.platform,
        )
