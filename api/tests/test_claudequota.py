"""Tests for the pure Claude remaining-window parser, including degraded/odd-shape cases."""

from __future__ import annotations

from datetime import UTC, datetime

from missioncontrol.claudequota import parse_claude_quota


def test_parses_fraction_and_percent_with_int_float_iso() -> None:
    usage = {
        "five_hour": {"utilization": 0.36, "resets_at": 1700000000.9},  # fraction, float epoch
        "seven_day": {"utilization": 12, "resets_at": "2026-06-28T17:59:00Z"},  # percent, ISO
    }
    q = parse_claude_quota(usage, now=1)  # now tiny => nothing stale
    by = {w.window: w for w in q.windows}
    assert q.available is True
    assert by["5h"].remaining_pct == 64.0 and by["5h"].used_pct == 36.0
    assert by["5h"].window_minutes == 300 and by["5h"].resets_at == 1700000000
    assert by["5h"].blocked is False and by["5h"].stale is False
    assert by["weekly"].remaining_pct == 88.0
    expected = int(datetime(2026, 6, 28, 17, 59, tzinfo=UTC).timestamp())
    assert by["weekly"].resets_at == expected


def test_blocked_when_full_and_no_resets() -> None:
    q = parse_claude_quota({"five_hour": {"utilization": 1.0}})
    w = q.windows[0]
    assert w.remaining_pct == 0.0 and w.blocked is True
    assert w.resets_at is None and w.stale is False  # now is None => never stale


def test_marks_stale_after_reset() -> None:
    q = parse_claude_quota({"five_hour": {"utilization": 0.5, "resets_at": 100}}, now=200)
    assert q.windows[0].stale is True


def test_clamps_out_of_range_utilization() -> None:
    q = parse_claude_quota({"five_hour": {"utilization": 150}, "seven_day": {"utilization": -5}})
    by = {w.window: w for w in q.windows}
    assert by["5h"].remaining_pct == 0.0 and by["5h"].blocked is True  # 150% clamps to full
    assert by["weekly"].remaining_pct == 100.0  # negative clamps to empty-used


def test_skips_non_dict_and_non_numeric_windows() -> None:
    q = parse_claude_quota({"five_hour": "nope", "seven_day": {"utilization": "bad"}})
    assert q.available is False and q.degraded == "no usable usage windows"


def test_bool_utilization_skipped_and_bad_iso_resets_none() -> None:
    usage = {
        "five_hour": {"utilization": True, "resets_at": 5},  # bool util => skipped
        "seven_day": {"utilization": 0.2, "resets_at": "bad-date"},  # bad ISO => resets None
    }
    q = parse_claude_quota(usage)
    assert [w.window for w in q.windows] == ["weekly"]
    assert q.windows[0].resets_at is None


def test_resets_bool_and_unknown_type_are_none() -> None:
    q = parse_claude_quota(
        {"five_hour": {"utilization": 0.1, "resets_at": True}},  # bool resets => None
    )
    assert q.windows[0].resets_at is None
    # unknown resets type (list) => None; now set + resets None => not stale
    q2 = parse_claude_quota({"seven_day": {"utilization": 0.1, "resets_at": []}}, now=5)
    assert q2.windows[0].resets_at is None and q2.windows[0].stale is False


def test_not_an_object_degrades() -> None:
    assert parse_claude_quota(None).available is False
    assert parse_claude_quota([]).degraded == "usage response was not an object"
