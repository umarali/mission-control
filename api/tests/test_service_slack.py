"""Behavioral tests for the Slack wiring in record_snapshot (dedup + degraded status).

The network seam (slacksource.fetch_slack_feed) is monkeypatched, so these run without a token and
without touching Slack — they pin the *glue*: items are stored once, and a degraded feed records a
single status row that doesn't repeat while the reason is unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import missioncontrol.service as svc
from missioncontrol.models import SlackFeed, SlackItem


def _item(ts: int, text: str = "ping") -> SlackItem:
    return SlackItem(
        kind="dm",
        channel="direct message",
        channel_id="D1",
        author="Alice",
        text=text,
        ts=float(ts),
        slack_ts=f"{ts}.000100",
        permalink=None,
    )


def _slack_rows(kind: str) -> list[object]:
    return [e for e in svc.get_store().recent(limit=500, surface="slack") if e.type == kind]


def test_slack_items_recorded_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MC_DB_PATH", str(tmp_path / "events.db"))
    svc.get_store().init()
    feed = SlackFeed(available=True, items=[_item(100), _item(200)])
    monkeypatch.setattr(svc, "slack_enabled", lambda: True)
    monkeypatch.setattr(svc, "fetch_slack_feed", lambda: feed)

    svc.record_snapshot()
    svc.record_snapshot()  # second poll returns the same messages -> must dedup on slack_ts

    msgs = svc.get_store().recent(limit=500, surface="slack")
    dms = [e for e in msgs if e.type == "slack.dm"]
    assert len(dms) == 2
    assert {e.payload["slack_ts"] for e in dms} == {"100.000100", "200.000100"}


def test_slack_degraded_status_not_spammed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MC_DB_PATH", str(tmp_path / "events.db"))
    svc.get_store().init()
    monkeypatch.setattr(svc, "slack_enabled", lambda: True)
    monkeypatch.setattr(
        svc, "fetch_slack_feed", lambda: SlackFeed(available=False, degraded="invalid_auth")
    )

    svc.record_snapshot()
    svc.record_snapshot()  # same reason -> no duplicate status row

    statuses = _slack_rows("collector.status")
    assert len(statuses) == 1
    assert statuses[0].payload["degraded"] == "invalid_auth"


def test_slack_skipped_when_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MC_DB_PATH", str(tmp_path / "events.db"))
    svc.get_store().init()
    monkeypatch.setattr(svc, "slack_enabled", lambda: False)
    # If this were called it would raise; disabled means it must never run.
    monkeypatch.setattr(svc, "fetch_slack_feed", lambda: 1 / 0)

    svc.record_snapshot()

    assert svc.get_store().recent(limit=500, surface="slack") == []
