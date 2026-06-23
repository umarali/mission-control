"""Pure alert logic: turn a quota snapshot into actionable throttle / headroom signals.

Credential-free, no I/O. Shared by the event store (alert rows) and the OS notifier so the
"when do we warn?" rule lives in exactly one place. Thresholds mirror the dashboard so the UI,
the stored events, and the desktop notification never disagree.

Vendor-neutral by construction: it scans every agent in the snapshot that exposes ``windows``;
an agent with no remaining-window data (e.g. Claude consumed-only in v1) simply yields nothing.
"""

from __future__ import annotations

from typing import Any

from .models import Alert

CRIT_PCT = 5.0  # at/under this remaining %, throttle risk is imminent
WARN_PCT = 20.0  # at/under this, caution
HEADROOM_PCT = 40.0  # above this, plenty left
HEADROOM_RESET_FRAC = (
    0.2  # ...but resetting within the final 20% of the window => use-it-or-lose-it
)


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _window_alert(surface: str, w: dict[str, Any], now: int | None) -> Alert | None:
    win = w.get("window")
    label = win if isinstance(win, str) else "unknown"
    remaining = _num(w.get("remaining_pct"))
    raw_reset = w.get("resets_at")
    resets_at = raw_reset if isinstance(raw_reset, int) else None
    blocked = bool(w.get("blocked"))

    if blocked or (remaining is not None and remaining <= 0):
        return Alert(
            kind="throttle",
            surface=surface,
            window=label,
            severity="crit",
            message=f"{surface} {label} window exhausted — you are throttled.",
            remaining_pct=remaining,
            resets_at=resets_at,
        )
    if remaining is None:
        return None
    if remaining < CRIT_PCT:
        return Alert(
            kind="throttle",
            surface=surface,
            window=label,
            severity="crit",
            message=f"{surface} {label}: only {remaining:g}% left — throttle risk.",
            remaining_pct=remaining,
            resets_at=resets_at,
        )
    if remaining < WARN_PCT:
        return Alert(
            kind="throttle",
            surface=surface,
            window=label,
            severity="warn",
            message=f"{surface} {label}: {remaining:g}% left — running low.",
            remaining_pct=remaining,
            resets_at=resets_at,
        )

    wm = w.get("window_minutes")
    if (
        remaining > HEADROOM_PCT
        and isinstance(wm, int)
        and wm > 0
        and resets_at is not None
        and now is not None
    ):
        frac = (resets_at - now) / (wm * 60)
        if 0 < frac < HEADROOM_RESET_FRAC:
            return Alert(
                kind="headroom",
                surface=surface,
                window=label,
                severity="warn",
                message=f"{surface} {label}: {remaining:g}% unused and resetting soon — "
                "queue work now or lose it.",
                remaining_pct=remaining,
                resets_at=resets_at,
            )
    return None


def alerts_from_snapshot(snap: dict[str, Any]) -> list[Alert]:
    """Return every throttle/headroom alert implied by a quota snapshot."""
    gen = snap.get("generated_at")
    now = gen if isinstance(gen, int) else None
    out: list[Alert] = []
    for surface, data in snap.items():
        if surface == "generated_at" or not isinstance(data, dict):
            continue
        windows = data.get("windows")
        if not isinstance(windows, list):
            continue
        for w in windows:
            if not isinstance(w, dict):
                continue
            alert = _window_alert(surface, w, now)
            if alert is not None:
                out.append(alert)
    return out
