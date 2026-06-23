"""Tests for the pure notification policy + argv building (the OS spawn is the osnotify seam)."""

from __future__ import annotations

from missioncontrol.models import Alert
from missioncontrol.notify import (
    Notifier,
    alert_key,
    notifiable,
    notification_text,
    notify_argv,
)


def _alert(kind: str = "throttle", severity: str = "crit", window: str = "5h") -> Alert:
    return Alert(
        kind=kind,
        surface="codex",
        window=window,
        severity=severity,
        message=f"codex {window}: low",
        remaining_pct=3.0,
        resets_at=None,
    )


def test_alert_key_includes_severity() -> None:
    assert alert_key(_alert(severity="warn")) != alert_key(_alert(severity="crit"))


def test_notifiable_fires_only_new_alerts() -> None:
    a = _alert()
    fire, active = notifiable([a], set())
    assert fire == [a] and active == {alert_key(a)}
    # Same alert still active next poll => no re-fire.
    fire2, active2 = notifiable([a], active)
    assert fire2 == [] and active2 == active


def test_notifiable_rearms_after_clear() -> None:
    a = _alert()
    _, active = notifiable([a], set())
    # Alert clears (empty snapshot) ...
    fire_cleared, active_cleared = notifiable([], active)
    assert fire_cleared == [] and active_cleared == set()
    # ... then returns => fires again.
    fire_again, _ = notifiable([a], active_cleared)
    assert fire_again == [a]


def test_notifiable_dedups_identical_keys() -> None:
    a = _alert()
    fire, active = notifiable([a, _alert()], set())
    assert len(fire) == 1 and len(active) == 1


def test_notification_text_is_calm_and_titled() -> None:
    title, body = notification_text(_alert())
    assert title == "Mission Control — codex 5h"
    assert body == "codex 5h: low"


def test_notify_argv_macos() -> None:
    argv = notify_argv("Darwin", "T", "B")
    assert argv is not None
    assert argv[0] == "/usr/bin/osascript" and argv[1] == "-e"
    assert "display notification" in argv[2] and '"B"' in argv[2] and '"T"' in argv[2]


def test_notify_argv_linux_with_and_without_notifier() -> None:
    argv = notify_argv("Linux", "T", "B", notify_send="/usr/bin/notify-send")
    assert argv == ["/usr/bin/notify-send", "-a", "Mission Control", "T", "B"]
    assert notify_argv("Linux", "T", "B", notify_send=None) is None


def test_notify_argv_unknown_platform_is_none() -> None:
    assert notify_argv("Plan9", "T", "B") is None


def test_notifier_fires_via_injected_sender_then_dedups() -> None:
    sent: list[tuple[str, str]] = []
    n = Notifier(lambda title, body: sent.append((title, body)) or True)
    n.process([_alert()])
    n.process([_alert()])  # still active => no second send
    assert len(sent) == 1
