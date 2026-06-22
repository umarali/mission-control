"""Tests for the pure Codex quota parser, including degraded cases."""

from __future__ import annotations

from typing import Any

from missioncontrol.codex import parse_codex_quota


def _token_count(rate_limits: dict[str, Any], *, wrap: bool = True) -> dict[str, Any]:
    payload = {"type": "token_count", "rate_limits": rate_limits}
    return {"payload": payload} if wrap else payload


def test_primary_and_secondary_windows() -> None:
    rl = {
        "primary": {"window_minutes": 300, "used_percent": 1.0, "resets_at": 1782177309},
        "secondary": {"window_minutes": 10080, "used_percent": 43.0, "resets_at": 1782360743},
    }
    q = parse_codex_quota([_token_count(rl)])
    assert q.available is True
    by = {w.window: w for w in q.windows}
    assert by["5h"].remaining_pct == 99.0
    assert by["5h"].resets_at == 1782177309
    assert by["weekly"].remaining_pct == 57.0
    assert by["weekly"].blocked is False


def test_uses_last_token_count() -> None:
    first = _token_count({"primary": {"window_minutes": 300, "used_percent": 5.0}})
    last = _token_count({"primary": {"window_minutes": 300, "used_percent": 80.0}})
    q = parse_codex_quota([first, {"payload": {"type": "other"}}, last])
    assert q.windows[0].remaining_pct == 20.0


def test_flat_payload_without_wrapper() -> None:
    rl = {"primary": {"window_minutes": 300, "used_percent": 10.0}}
    q = parse_codex_quota([_token_count(rl, wrap=False)])
    assert q.available is True
    assert q.windows[0].remaining_pct == 90.0


def test_no_token_count_is_degraded() -> None:
    q = parse_codex_quota([{"payload": {"type": "message"}}, {"foo": "bar"}])
    assert q.available is False
    assert q.degraded is not None


def test_rate_limits_without_usable_windows() -> None:
    q = parse_codex_quota([_token_count({"tertiary": {"window_minutes": 1}})])
    assert q.available is False
    assert q.degraded == "rate_limits had no usable windows"


def test_unknown_and_missing_window_minutes_and_null_used() -> None:
    rl = {
        "primary": {"window_minutes": 60, "used_percent": None},  # -> "60min", remaining None
        "secondary": {"used_percent": 20.0},  # no window_minutes -> "unknown"
    }
    q = parse_codex_quota([_token_count(rl)])
    by = {w.window: w for w in q.windows}
    assert by["60min"].remaining_pct is None
    assert by["60min"].window_minutes == 60
    assert by["unknown"].window_minutes is None
    assert by["unknown"].remaining_pct == 80.0


def test_blocked_by_flag_and_by_zero_remaining() -> None:
    rl = {
        "primary": {"window_minutes": 300, "used_percent": 100.0},  # remaining 0 -> blocked
        "secondary": {"window_minutes": 10080, "used_percent": 50.0,
                      "rate_limit_reached_type": "weekly"},  # flag -> blocked
    }
    q = parse_codex_quota([_token_count(rl)])
    by = {w.window: w for w in q.windows}
    assert by["5h"].blocked is True
    assert by["weekly"].blocked is True


def test_token_count_without_rate_limits_is_skipped() -> None:
    records = [
        {"payload": {"type": "token_count"}},  # no rate_limits -> skipped
        _token_count({"primary": {"window_minutes": 300, "used_percent": 0.0}}),
    ]
    q = parse_codex_quota(records)
    assert q.available is True
    assert q.windows[0].remaining_pct == 100.0
