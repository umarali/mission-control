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
from .codex import parse_codex_quota
from .events import events_from_snapshot
from .models import ClaudeConsumed, CodexQuota, Transcript
from .notify import Notifier
from .osnotify import os_send
from .paths import newest_claude_transcript, newest_codex_rollout, read_jsonl
from .store import EventStore
from .transcript import DEFAULT_LIMIT, render_transcript

MAX_EVENTS = 5000  # retention cap: keep the store bounded for a local-first tool

_store = EventStore()
_notifier = Notifier(os_send)


def get_store() -> EventStore:
    """The process-wide event store (lazily pathed; honors MC_DB_PATH)."""
    return _store


def snapshot() -> dict[str, Any]:
    """Read both agents' newest local files and return the current quota/usage snapshot."""
    codex_path = newest_codex_rollout()
    if codex_path is not None:
        codex = parse_codex_quota(read_jsonl(codex_path))
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

    return {
        "generated_at": int(time.time()),
        "codex": asdict(codex),
        "claude": asdict(claude),
    }


def record_snapshot() -> dict[str, Any]:
    """Compute a snapshot, persist its derived events, prune, and return it.

    Degrade, never lie: a store failure must not break the live read, so it is swallowed here
    (the history/timeline feature degrades, the gauges do not).
    """
    snap = snapshot()
    try:
        _store.append(events_from_snapshot(snap))
        _store.prune(MAX_EVENTS)
    except Exception:  # noqa: BLE001  # reason: store hiccup must never break the live snapshot
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
