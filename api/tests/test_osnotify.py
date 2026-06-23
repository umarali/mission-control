"""The OS-notifier seam is omitted from the unit gate, but it must always degrade, never raise."""

from __future__ import annotations

import missioncontrol.osnotify as osnotify


def test_os_send_returns_bool_and_never_raises() -> None:
    assert isinstance(osnotify.os_send("title", "body"), bool)


def test_os_send_false_when_no_notifier(monkeypatch: object) -> None:
    mp = monkeypatch  # typed loosely to avoid importing the plugin's type
    mp.setattr(osnotify.platform, "system", lambda: "Plan9")  # type: ignore[attr-defined]
    assert osnotify.os_send("t", "b") is False
