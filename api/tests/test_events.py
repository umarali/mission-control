"""Tests for the pure event-derivation logic (scrubbing + snapshot -> rows)."""

from __future__ import annotations

from missioncontrol.events import events_from_snapshot, make_event
from missioncontrol.redact import REDACTED


def test_make_event_scrubs_payload_and_defaults() -> None:
    e = make_event("codex", "codex.collector", "quota.snapshot", ts=42, payload={"token": "x"})
    assert e.severity == "info"  # default
    assert e.payload == {"token": REDACTED}
    assert e.session_id is None and e.work_thread_id is None


def test_make_event_clamps_unknown_severity() -> None:
    assert make_event("codex", "s", "t", ts=1, severity="bogus").severity == "info"
    assert make_event("codex", "s", "t", ts=1, severity="crit").severity == "crit"


def test_snapshot_yields_quota_and_status_rows() -> None:
    snap = {
        "generated_at": 100,
        "codex": {"available": True, "windows": [{"window": "5h", "remaining_pct": 80.0}]},
        "claude": {"available": False, "degraded": "no transcripts"},
    }
    events = events_from_snapshot(snap)
    by_type = {e.type for e in events}
    assert "quota.snapshot" in by_type
    assert "collector.status" in by_type
    codex_ev = next(e for e in events if e.surface == "codex" and e.type == "quota.snapshot")
    assert codex_ev.ts == 100 and codex_ev.severity == "info"
    claude_ev = next(e for e in events if e.surface == "claude")
    assert claude_ev.severity == "warn" and claude_ev.payload == {"degraded": "no transcripts"}


def test_snapshot_emits_alert_rows() -> None:
    snap = {
        "generated_at": 100,
        "codex": {"available": True, "windows": [{"window": "5h", "remaining_pct": 2.0}]},
    }
    events = events_from_snapshot(snap)
    alert = next(e for e in events if e.type == "alert.throttle")
    assert alert.severity == "crit" and alert.payload["kind"] == "throttle"


def test_snapshot_skips_non_dict_and_generated_at() -> None:
    events = events_from_snapshot({"generated_at": 5, "noise": 7})
    assert events == []


def test_missing_generated_at_defaults_ts_to_zero() -> None:
    events = events_from_snapshot({"codex": {"available": True, "windows": []}})
    assert events[0].ts == 0
