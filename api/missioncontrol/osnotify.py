"""OS-notifier subprocess seam (issue #11). Isolated + omitted from the unit gate.

Honors the CLAUDE.md subprocess rule: absolute path, fixed argv, never a shell, output captured
with a timeout and never logged raw. macOS uses the built-in osascript; Linux uses notify-send if
present. Anything else (or a missing/failed notifier) degrades to a quiet False — never raises.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess

from .notify import notify_argv


def os_send(title: str, body: str) -> bool:
    """Best-effort desktop notification. Returns True only if the notifier was spawned cleanly."""
    system = platform.system()
    notify_send = shutil.which("notify-send") if system == "Linux" else None
    argv = notify_argv(system, title, body, notify_send=notify_send)
    if argv is None or not os.path.isabs(argv[0]) or not os.path.exists(argv[0]):
        return False
    try:
        subprocess.run(argv, capture_output=True, timeout=5, check=False)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
