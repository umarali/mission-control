"""Wire the filesystem seam to the pure parsers and produce a JSON-able snapshot.

Thin glue (excluded from unit-coverage); the logic it calls is fully tested.
"""

from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .alerts import alerts_from_snapshot
from .claude import parse_claude_consumed
from .claudecreds import claude_quota_enabled, fetch_claude_usage
from .claudequota import parse_claude_quota
from .codex import parse_codex_quota
from .events import events_from_snapshot, make_event
from .models import ClaudeConsumed, ClaudeQuota, CodexQuota, Transcript
from .notify import Notifier
from .osnotify import os_send
from .paths import newest_claude_transcript, newest_codex_rollout, read_jsonl
from .slack import slack_events
from .slacksource import fetch_slack_feed, slack_enabled
from .store import EventStore
from .transcript import DEFAULT_LIMIT, render_transcript

MAX_EVENTS = 5000  # retention cap: keep the store bounded for a local-first tool
SLACK_DEDUP_WINDOW = 1000  # recent slack rows scanned to avoid re-storing the same message

_store = EventStore()
_notifier = Notifier(os_send)


def get_store() -> EventStore:
    """The process-wide event store (lazily pathed; honors MC_DB_PATH)."""
    return _store


def _claude_quota(now: int) -> ClaudeQuota:
    """Claude remaining windows from the OAuth usage endpoint (credentialed, opt-in)."""
    usage = fetch_claude_usage()
    if usage is not None:
        return parse_claude_quota(usage, now=now)
    if claude_quota_enabled():
        return ClaudeQuota(available=False, degraded="Claude usage unavailable (token or endpoint)")
    return ClaudeQuota(
        available=False, degraded="set MC_ENABLE_CLAUDE_QUOTA=1 to show remaining quota"
    )


def snapshot() -> dict[str, Any]:
    """Read both agents' newest local files and return the current quota/usage snapshot."""
    now = int(time.time())

    codex_path = newest_codex_rollout()
    if codex_path is not None:
        codex = parse_codex_quota(read_jsonl(codex_path), now=now)
    else:
        codex = CodexQuota(available=False, degraded="no Codex sessions found")

    claude_path = newest_claude_transcript()
    if claude_path is not None:
        claude = parse_claude_consumed(read_jsonl(claude_path))
    else:
        claude = ClaudeConsumed(
            available=False,
            input_tokens=0,
            output_tokens=0,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            total_tokens=0,
            events=0,
            degraded="no Claude transcripts found",
        )

    # Claude gets BOTH: remaining-window gauges (primary) + the consumed-token meter (secondary).
    claude_dict = asdict(claude)
    cq = _claude_quota(now)
    claude_dict["windows"] = [asdict(w) for w in cq.windows]
    claude_dict["quota_available"] = cq.available
    claude_dict["quota_degraded"] = cq.degraded

    return {"generated_at": now, "codex": asdict(codex), "claude": claude_dict}


def _record_slack() -> None:
    """Fetch Slack buried items and append the new ones (dedup on slack_ts).

    Opt-in: only called when SLACK_TOKEN is set. Degrade-never-lie: an unavailable feed records a
    single ``collector.status`` row, but only when the reason changes (so a bad token does not spam
    the timeline). Read-only throughout; the token never reaches the store.
    """
    feed = fetch_slack_feed()
    if not feed.available:
        recent = _store.recent(limit=50, surface="slack")
        last_status = next((e for e in recent if e.type == "collector.status"), None)
        if last_status is None or last_status.payload.get("degraded") != feed.degraded:
            _store.append(
                [
                    make_event(
                        "slack",
                        "slack.collector",
                        "collector.status",
                        ts=int(time.time()),
                        severity="warn",
                        payload={"degraded": feed.degraded},
                    )
                ]
            )
        return
    events = slack_events(feed)
    if not events:
        return
    seen = {
        e.payload.get("slack_ts") for e in _store.recent(limit=SLACK_DEDUP_WINDOW, surface="slack")
    }
    fresh = [e for e in events if e.payload.get("slack_ts") not in seen]
    if fresh:
        _store.append(fresh)


def record_snapshot() -> dict[str, Any]:
    """Compute a snapshot, persist its derived events (+ Slack, if enabled), prune, and return it.

    Degrade, never lie: a store/collector failure must not break the live read, so each side
    effect is swallowed independently (the history/timeline degrades, the gauges do not).
    """
    snap = snapshot()
    try:
        _store.append(events_from_snapshot(snap))
    except Exception:  # noqa: BLE001  # reason: store hiccup must never break the live snapshot
        pass
    try:
        if slack_enabled():
            _record_slack()
    except Exception:  # noqa: BLE001  # reason: a Slack hiccup must never break the read path
        pass
    try:
        _store.prune(MAX_EVENTS)
    except Exception:  # noqa: BLE001  # reason: prune is best-effort retention, not correctness
        pass
    try:
        _notifier.process(alerts_from_snapshot(snap))
    except Exception:  # noqa: BLE001  # reason: a notifier hiccup must never break the read path
        pass
    return snap


def transcript(agent: str, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Render the newest local transcript for an agent into a read-only list of turns."""
    if agent == "claude":
        path = newest_claude_transcript()
    elif agent == "codex":
        path = newest_codex_rollout()
    else:
        return asdict(Transcript(available=False, agent=agent, degraded="unknown agent"))

    if path is None:
        return asdict(
            Transcript(available=False, agent=agent, degraded=f"no {agent} session found")
        )

    turns = render_transcript(agent, read_jsonl(path), limit=limit)
    if not turns:
        return asdict(Transcript(available=False, agent=agent, degraded="no readable turns"))
    return asdict(Transcript(available=True, agent=agent, turns=turns, session_id=Path(path).stem))
