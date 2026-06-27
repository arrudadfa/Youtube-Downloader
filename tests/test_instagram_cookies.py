"""Testes de exportação de cookies Instagram."""

from __future__ import annotations

import json
from pathlib import Path

from src.core.instagram_cookies import (
    export_cookies_from_session,
    resolve_gallery_cookies_path,
    session_has_login,
    write_netscape_cookies,
)


def test_session_has_login_true(tmp_path: Path) -> None:
    session = tmp_path / "session.json"
    session.write_text(
        json.dumps({"authorization_data": {"sessionid": "abc123", "ds_user_id": "999"}}),
        encoding="utf-8",
    )
    assert session_has_login(session) is True


def test_session_has_login_false(tmp_path: Path) -> None:
    session = tmp_path / "session.json"
    session.write_text(json.dumps({"cookies": {}}), encoding="utf-8")
    assert session_has_login(session) is False


def test_export_cookies_from_session(tmp_path: Path) -> None:
    session = tmp_path / "session.json"
    output = tmp_path / "cookies.txt"
    session.write_text(
        json.dumps({"authorization_data": {"sessionid": "sess", "ds_user_id": "42"}}),
        encoding="utf-8",
    )

    assert export_cookies_from_session(session, output) is True
    content = output.read_text(encoding="utf-8")
    assert content.startswith("# Netscape HTTP Cookie File")
    assert "sessionid\tsess" in content
    assert "ds_user_id\t42" in content


def test_write_netscape_cookies(tmp_path: Path) -> None:
    output = tmp_path / "cookies.txt"
    write_netscape_cookies({"sessionid": "x"}, output)
    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "# Netscape HTTP Cookie File"
    assert "sessionid\tx" in lines[-1]


def test_resolve_prefers_manual_cookies(tmp_path: Path) -> None:
    session = tmp_path / "session.json"
    manual = tmp_path / "manual.txt"
    cache = tmp_path / "cache.txt"
    session.write_text(json.dumps({"authorization_data": {"sessionid": "s"}}), encoding="utf-8")
    manual.write_text("# Netscape HTTP Cookie File\n\n", encoding="utf-8")

    resolved = resolve_gallery_cookies_path(session, manual, cache)
    assert resolved == manual
