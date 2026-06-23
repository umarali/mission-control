"""Local command-exec seam for jump-to-agent (the I/O seam; omitted from the unit gate).

This is the first surface that runs a command rather than only reading, so it is locked down:
it is OFF by default and only acts when MC_ENABLE_JUMP=1 is explicitly set (non-invasive by
default). Even then it spawns by absolute path + fixed argv, never a shell, and degrades to
False on any failure. The endpoint always returns the resume command regardless, so the UI is
useful even with launching disabled.
"""

from __future__ import annotations

import os
import shutil
import subprocess


def jump_enabled() -> bool:
    return os.environ.get("MC_ENABLE_JUMP") == "1"


def launch_resume(argv: list[str]) -> bool:
    """Best-effort local launch of the resume command. Returns True only if actually spawned."""
    if not jump_enabled() or not argv:
        return False
    binary = shutil.which(argv[0])
    if binary is None:
        return False
    try:
        subprocess.Popen(  # noqa: S603  # reason: fixed argv, no shell; binary resolved absolutely
            [binary, *argv[1:]],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False
