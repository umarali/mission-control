"""Pure event derivation: turn a quota snapshot into normalized, scrubbed event rows.

Credential-free, no I/O. The store (store.py) persists whatever this returns; because every
payload is run through ``scrub_payload`` here, the store can never hold a secret (PLAN.md §5).

In v1 the only rows are quota snapshots, collector status, and alerts (PLAN.md §5). The schema
and the I/O live in store.py; this module is the testable logic around that seam.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .alerts import alerts_from_snapshot
from .models import Event
from .redact import scrub_payload

SEVERITIES = ("info", "warn", "crit")


def make_event(
    surface: str,
    source: str,
    type: str,
    *,
    ts: int,
    severity: str = "info",
    session_id: str | None = None,
    work_thread_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Event:
    """Build one event, scrubbing the payload and clamping an unknown severity to ``info``."""
    sev = severity if severity in SEVERITIES else "info"
    return Event(
        surface=surface,
        source=source,
        type=type,
        ts=ts,
        severity=sev,
        session_id=session_id,
        work_thread_id=work_thread_id,
        payload=scrub_payload(payload or {}),
    )


def events_from_snapshot(snap: dict[str, Any]) -> list[Event]:
    """Derive the event rows a quota snapshot implies: per-agent status + any alerts."""
    gen = snap.get("generated_at")
    ts = gen if isinstance(gen, int) else 0
    out: list[Event] = []

    for surface, data in snap.items():
        if surface == "generated_at" or not isinstance(data, dict):
            continue
        if data.get("available"):
            out.append(
                make_event(surface, f"{surface}.collector", "quota.snapshot", ts=ts, payload=data)
            )
        else:
            out.append(
                make_event(
                    surface,
                    f"{surface}.collector",
                    "collector.status",
                    ts=ts,
                    severity="warn",
                    payload={"degraded": data.get("degraded")},
                )
            )

    for alert in alerts_from_snapshot(snap):
        out.append(
            make_event(
                alert.surface,
                "alerts",
                f"alert.{alert.kind}",
                ts=ts,
                severity=alert.severity,
                payload=asdict(alert),
            )
        )

    return out
