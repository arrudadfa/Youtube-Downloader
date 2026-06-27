"""Exportação de cookies Instagram para gallery-dl (formato Netscape)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from instagrapi import Client

INSTAGRAM_COOKIE_DOMAIN = ".instagram.com"
NETSCAPE_HEADER = "# Netscape HTTP Cookie File\n\n"


def session_has_login(session_path: Path) -> bool:
    """True se a sessão instagrapi contém sessionid."""
    if not session_path.exists():
        return False
    try:
        data = json.loads(session_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(_collect_cookies(data).get("sessionid"))


def _collect_cookies(session_data: dict) -> dict[str, str]:
    cookies: dict[str, str] = {}
    raw = session_data.get("cookies") or {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if value is not None and str(value).strip():
                cookies[str(key)] = str(value)

    auth = session_data.get("authorization_data") or {}
    if isinstance(auth, dict):
        for key in ("sessionid", "ds_user_id"):
            value = auth.get(key)
            if value is not None and str(value).strip():
                cookies[key] = str(value)

    return cookies


def write_netscape_cookies(
    cookies: dict[str, str],
    output_path: Path,
    domain: str = INSTAGRAM_COOKIE_DOMAIN,
) -> None:
    """Grava cookies no formato cookies.txt (Netscape) usado pelo gallery-dl."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [NETSCAPE_HEADER]
    expires = str(int(time.time()) + 365 * 24 * 3600)

    for name, value in cookies.items():
        if not value:
            continue
        secure = "TRUE" if name in {"sessionid", "ds_user_id"} else "FALSE"
        lines.append(
            f"{domain}\tTRUE\t/\t{secure}\t{expires}\t{name}\t{value}\n"
        )

    output_path.write_text("".join(lines), encoding="utf-8")


def export_cookies_from_session(session_path: Path, output_path: Path) -> bool:
    """Exporta cookies da sessão instagrapi. Retorna False se não houver sessionid."""
    if not session_path.exists():
        return False

    try:
        session_data = json.loads(session_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    cookies = _collect_cookies(session_data)
    if not cookies.get("sessionid"):
        return False

    write_netscape_cookies(cookies, output_path)
    return True


def export_cookies_from_client(client: Client, output_path: Path) -> bool:
    """Exporta cookies do client instagrapi autenticado."""
    cookies = dict(client.cookie_dict or {})
    settings = client.get_settings()
    cookies.update(_collect_cookies(settings))
    if not cookies.get("sessionid"):
        return False
    write_netscape_cookies(cookies, output_path)
    return True


def resolve_gallery_cookies_path(
    session_path: Path,
    manual_path: Path | None,
    cache_path: Path,
) -> Path | None:
    """
    Resolve arquivo de cookies para gallery-dl.
    Prioridade: manual > cache exportado da sessão instagrapi.
    """
    if manual_path and manual_path.exists():
        return manual_path

    session_mtime = session_path.stat().st_mtime if session_path.exists() else 0
    cache_mtime = cache_path.stat().st_mtime if cache_path.exists() else 0

    if not cache_path.exists() or session_mtime > cache_mtime:
        if not export_cookies_from_session(session_path, cache_path):
            if cache_path.exists():
                return cache_path
            return None

    return cache_path if cache_path.exists() else None
