"""Validação e extração de URLs de vídeo."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from src.core.platforms import Platform, detect_platform

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    platform: Optional[str]
    url: Optional[str] = None
    error: Optional[str] = None


def extract_url(text: str) -> Optional[str]:
    """Extrai a primeira URL HTTP(S) de uma mensagem."""
    match = _URL_PATTERN.search(text.strip())
    return match.group(0).rstrip(".,)") if match else None


def validate_url(url: str) -> ValidationResult:
    """Valida URL e retorna plataforma detectada."""
    url = url.strip()
    if not url.lower().startswith("https://"):
        return ValidationResult(
            is_valid=False,
            platform=None,
            error="Apenas URLs HTTPS são suportadas.",
        )

    platform = detect_platform(url)
    if platform is None:
        return ValidationResult(
            is_valid=False,
            platform=None,
            url=url,
            error="Plataforma não suportada.",
        )

    return ValidationResult(is_valid=True, platform=platform.value, url=url)


def is_supported_url(url: str) -> bool:
    return validate_url(url).is_valid
