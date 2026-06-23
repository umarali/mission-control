"""Tests for the pure localhost-hardening predicates."""

from __future__ import annotations

from missioncontrol.security import (
    host_allowed,
    new_session_token,
    origin_allowed,
    token_ok,
)


def test_origin_allowed_passes_allowlist_and_empty() -> None:
    assert origin_allowed(None) is True
    assert origin_allowed("") is True
    assert origin_allowed("http://localhost:3000") is True
    assert origin_allowed("http://127.0.0.1:3000") is True


def test_origin_allowed_rejects_foreign_site() -> None:
    assert origin_allowed("https://evil.example") is False
    assert origin_allowed("http://localhost:3001") is False


def test_host_allowed_passes_localhost_variants_and_empty() -> None:
    assert host_allowed(None) is True
    assert host_allowed("localhost:3000") is True
    assert host_allowed("127.0.0.1:8787") is True
    assert host_allowed("127.0.0.1") is True
    assert host_allowed("[::1]:8787") is True


def test_host_allowed_rejects_rebinding_host() -> None:
    assert host_allowed("attacker.com") is False
    assert host_allowed("attacker.com:8787") is False
    assert host_allowed("evil.localhost.attacker.com") is False


def test_session_token_is_random_and_nonempty() -> None:
    a, b = new_session_token(), new_session_token()
    assert a and b and a != b


def test_token_ok_compares_constant_time() -> None:
    tok = new_session_token()
    assert token_ok(tok, tok) is True
    assert token_ok("wrong", tok) is False
    assert token_ok(None, tok) is False
    assert token_ok("", tok) is False
