"""Pure builder for the "jump to agent" resume command (PLAN.md §8 — v1.5, first command-exec).

Credential-free, no I/O. Builds a fixed argv (never a shell string) for resuming an agent
session. The session id is validated hard: it must look like a real session id and must not
start with ``-`` — that closes argument-injection (a value like ``--dangerous-flag`` landing in
the positional slot) on top of the no-shell guarantee. Unknown agent or bad id => None.
"""

from __future__ import annotations

import re
from collections.abc import Callable

# First char is not a hyphen (no flag injection); then id-safe chars only; max 128.
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._][A-Za-z0-9._-]{0,127}$")

_BUILDERS: dict[str, Callable[[str], list[str]]] = {
    "claude": lambda sid: ["claude", "--resume", sid],
    "codex": lambda sid: ["codex", "resume", sid],
}


def resume_command(agent: str, session_id: str) -> list[str] | None:
    """Return the fixed argv to resume an agent session, or None if invalid."""
    builder = _BUILDERS.get(agent)
    if builder is None:
        return None
    if not isinstance(session_id, str) or not _SESSION_ID_RE.match(session_id):
        return None
    return builder(session_id)
