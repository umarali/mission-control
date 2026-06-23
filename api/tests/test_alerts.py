"""Tests for the pure alert logic, including the headroom / throttle boundaries."""

from __future__ import annotations

from typing import Any

from missioncontrol.alerts import alerts_from_snapshot


def _snap(
    windows: list[dict[str, Any]], *, now: int = 1000, surface: str = "codex"
) -> dict[str, Any]:
    return {"generated_at": now, surface: {"available": True, "windows": windows}}


def test_throttle_crit_when_blocked() -> None:
    a = alerts_from_snapshot(_snap([{"window": "5h", "remaining_pct": 50.0, "blocked": True}]))
    assert len(a) == 1
    assert a[0].kind == "throttle" and a[0].severity == "crit"


def test_throttle_crit_when_zero_remaining() -> None:
    a = alerts_from_snapshot(_snap([{"window": "5h", "remaining_pct": 0.0, "blocked": False}]))
    assert a[0].severity == "crit" and "exhausted" in a[0].message


def test_throttle_crit_under_five_pct() -> None:
    a = alerts_from_snapshot(_snap([{"window": "5h", "remaining_pct": 3.0, "blocked": False}]))
    assert a[0].severity == "crit" and a[0].remaining_pct == 3.0


def test_throttle_warn_under_twenty_pct() -> None:
    a = alerts_from_snapshot(_snap([{"window": "5h", "remaining_pct": 12.0, "blocked": False}]))
    assert a[0].severity == "warn" and a[0].kind == "throttle"


def test_healthy_window_yields_no_alert() -> None:
    a = alerts_from_snapshot(_snap([{"window": "5h", "remaining_pct": 80.0, "blocked": False}]))
    assert a == []


def test_stale_window_yields_no_alert() -> None:
    # A would-be crit (3% left) but stale: the number has rolled over, so do not alert on it.
    a = alerts_from_snapshot(
        _snap([{"window": "5h", "remaining_pct": 3.0, "blocked": False, "stale": True}])
    )
    assert a == []


def test_headroom_when_unused_and_resetting_soon() -> None:
    # 60% left, 5h window, resets in 30 min (< 20% of 300 min) => use-it-or-lose-it.
    w = {
        "window": "5h",
        "window_minutes": 300,
        "remaining_pct": 60.0,
        "resets_at": 1000 + 30 * 60,
        "blocked": False,
    }
    a = alerts_from_snapshot(_snap([w], now=1000))
    assert len(a) == 1 and a[0].kind == "headroom" and a[0].severity == "warn"


def test_no_headroom_when_reset_is_far_off() -> None:
    w = {
        "window": "5h",
        "window_minutes": 300,
        "remaining_pct": 60.0,
        "resets_at": 1000 + 200 * 60,  # > 20% of the window remaining
        "blocked": False,
    }
    assert alerts_from_snapshot(_snap([w], now=1000)) == []


def test_no_headroom_without_window_minutes_or_reset() -> None:
    assert alerts_from_snapshot(_snap([{"window": "5h", "remaining_pct": 60.0}])) == []
    w = {"window": "5h", "remaining_pct": 60.0, "resets_at": 1100}
    assert alerts_from_snapshot(_snap([w], now=1000)) == []


def test_null_remaining_is_skipped() -> None:
    assert alerts_from_snapshot(_snap([{"window": "5h", "remaining_pct": None}])) == []


def test_boolean_remaining_is_not_treated_as_number() -> None:
    # bool is a subclass of int; it must not be read as a percentage.
    assert alerts_from_snapshot(_snap([{"window": "5h", "remaining_pct": True}])) == []


def test_ignores_non_window_data_and_missing_now() -> None:
    snap = {
        "generated_at": "not-an-int",
        "claude": {"available": True, "total_tokens": 5},  # no "windows"
        "codex": {"available": False, "degraded": "x"},  # windows missing
        "noise": 7,
        "broken": {"windows": ["not-a-dict", {"window": "5h", "remaining_pct": 2.0}]},
    }
    a = alerts_from_snapshot(snap)
    assert len(a) == 1 and a[0].surface == "broken" and a[0].severity == "crit"
