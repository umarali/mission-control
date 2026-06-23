"""Tests for the pure redaction + payload-scrubbing helpers.

Token fixtures are built by concatenation so no real-looking secret literal lands in the tree
(the guard-secrets hook blocks those, and rightly so).
"""

from __future__ import annotations

from missioncontrol.redact import REDACTED, redact_text, scrub_payload

# Token-shaped fixtures assembled at runtime (no literal secret in source).
ANTHROPIC = "sk-ant-" + "A1b2C3d4E5f6G7h8J9k0"
OPENAI = "sk-" + "A1b2C3d4E5f6G7h8J9k0"
GITHUB = "ghp_" + "A1b2C3d4E5f6G7h8J9k0"
SLACK = "xoxb-" + "1234567890-abcDEF"
AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
JWT = "eyJ" + "hbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiIxMjM0" + "." + "s1gnatur3"
BEARER = "Bearer " + "A1b2C3d4E5f6G7h8J9k0"
_BEGIN = "-----BEGIN " + "RSA PRIVATE KEY" + "-----"
_END = "-----END " + "RSA PRIVATE KEY" + "-----"


def test_redacts_each_token_shape() -> None:
    for tok in (ANTHROPIC, OPENAI, GITHUB, SLACK, AWS, JWT, BEARER):
        masked = redact_text(f"prefix {tok} suffix")
        assert tok not in masked
        assert REDACTED in masked
        assert masked.startswith("prefix ") and masked.endswith(" suffix")


def test_redacts_pem_block() -> None:
    pem = f"{_BEGIN}\nMIIxxx\n{_END}"
    assert redact_text(f"key=[{pem}]") == f"key=[{REDACTED}]"


def test_clean_text_is_untouched() -> None:
    text = "Codex 5h 98% remaining, resets in 3h 12m"
    assert redact_text(text) == text


def test_scrub_masks_sensitive_keys_wholesale() -> None:
    payload = {
        "Authorization": "Bearer whatever-even-if-short",
        "api_key": "plain",
        "session-token": "x",
        "nested": {"client_secret": "y", "ok": "value"},
    }
    out = scrub_payload(payload)
    assert out["Authorization"] == REDACTED
    assert out["api_key"] == REDACTED
    assert out["session-token"] == REDACTED
    assert out["nested"]["client_secret"] == REDACTED
    assert out["nested"]["ok"] == "value"


def test_scrub_redacts_token_shaped_values_under_safe_keys() -> None:
    payload = {"note": f"leaked {ANTHROPIC} here", "items": [OPENAI, "fine"]}
    out = scrub_payload(payload)
    assert ANTHROPIC not in out["note"]
    assert out["items"][0] == REDACTED
    assert out["items"][1] == "fine"


def test_scrub_passes_through_non_string_scalars() -> None:
    payload = {"remaining_pct": 98.0, "blocked": False, "count": 3, "nothing": None}
    assert scrub_payload(payload) == payload


def test_scrub_handles_top_level_list_and_scalars() -> None:
    assert scrub_payload([1, "two", {"token": "z"}]) == [1, "two", {"token": REDACTED}]
    assert scrub_payload(42) == 42
