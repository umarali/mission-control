"""Out-of-tab OS notifications (issue #11): pure notification policy + argv building.

Alerts recompute every poll; we only want a desktop notification on the *transition into* an
alert state, not once every 30 s. ``Notifier`` is edge-triggered: it remembers which alert keys
are currently firing and notifies only the newly-firing ones (re-arming once an alert clears).

The actual subprocess spawn lives in osnotify.py (the seam); everything here is pure and the
sender is injected, so this module stays 100%-covered and the OS call is isolated.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from .models import Alert
from .redact import redact_text

NotifySender = Callable[[str, str], bool]


def alert_key(a: Alert) -> str:
    """Identity for dedup: severity is included so an escalation (warn->crit) re-notifies."""
    return f"{a.surface}:{a.window}:{a.kind}:{a.severity}"


def notifiable(alerts: list[Alert], previously_notified: set[str]) -> tuple[list[Alert], set[str]]:
    """Return (alerts to fire now, the new active key-set). Edge-triggered against the prior set."""
    active: dict[str, Alert] = {}
    for a in alerts:
        active.setdefault(alert_key(a), a)
    to_fire = [a for k, a in active.items() if k not in previously_notified]
    return to_fire, set(active)


def notification_text(a: Alert) -> tuple[str, str]:
    """Calm, control-room title + body (redacted defensively)."""
    title = f"Mission Control — {a.surface} {a.window}"
    return redact_text(title), redact_text(a.message)


def _applescript_str(s: str) -> str:
    # A JSON string literal is a valid AppleScript double-quoted string (\" and \\ escapes match).
    return json.dumps(s)


def notify_argv(
    system: str,
    title: str,
    body: str,
    *,
    osascript: str = "/usr/bin/osascript",
    notify_send: str | None = None,
) -> list[str] | None:
    """Build the fixed argv for the platform notifier, or None if none is available.

    Absolute path + fixed argv, never a shell (CLAUDE.md subprocess rule). Inputs are redacted.
    """
    t, b = redact_text(title), redact_text(body)
    if system == "Darwin":
        script = f"display notification {_applescript_str(b)} with title {_applescript_str(t)}"
        return [osascript, "-e", script]
    if system == "Linux" and notify_send:
        return [notify_send, "-a", "Mission Control", t, b]
    return None


class Notifier:
    """Stateful, edge-triggered dispatcher. Inject the sender (real one in service.py)."""

    def __init__(self, sender: NotifySender) -> None:
        self._notified: set[str] = set()
        self._sender = sender

    def process(self, alerts: list[Alert]) -> list[Alert]:
        """Fire notifications for newly-firing alerts; return what was fired."""
        to_fire, active = notifiable(alerts, self._notified)
        self._notified = active
        for a in to_fire:
            title, body = notification_text(a)
            self._sender(title, body)
        return to_fire
