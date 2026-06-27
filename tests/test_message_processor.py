"""Testes para message_processor."""

import pytest

from src.handlers.message_processor import (
    is_owner,
    should_charge_star,
    build_invoice_payload,
)


class TestAccessControl:
    def test_owner_is_free(self):
        assert is_owner(163177765) is True
        assert should_charge_star(163177765) is False

    def test_other_user_charged(self):
        assert is_owner(999999) is False
        assert should_charge_star(999999) is True


class TestInvoicePayload:
    def test_payload_contains_url_hash(self):
        payload = build_invoice_payload("https://youtube.com/watch?v=abc", 12345)
        assert payload.startswith("dl:")
        assert "12345" in payload
