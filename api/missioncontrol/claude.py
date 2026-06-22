"""Pure parser: Claude consumed-token totals from transcript `message.usage` records.

Credential-free. Input is already-parsed JSON objects; this module does no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import ClaudeConsumed

_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def parse_claude_consumed(records: Iterable[dict[str, Any]]) -> ClaudeConsumed:
    """Sum token usage across a Claude transcript's records."""
    totals: dict[str, int] = {k: 0 for k in _FIELDS}
    events = 0
    for obj in records:
        msg = obj.get("message")
        usage = msg.get("usage") if isinstance(msg, dict) else None
        if not isinstance(usage, dict):
            usage = obj.get("usage")
        if not isinstance(usage, dict):
            continue
        events += 1
        for k in _FIELDS:
            v = usage.get(k)
            if isinstance(v, int):
                totals[k] += v

    if events == 0:
        return ClaudeConsumed(
            available=False,
            input_tokens=0,
            output_tokens=0,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            total_tokens=0,
            events=0,
            degraded="no message.usage in transcript",
        )
    return ClaudeConsumed(
        available=True,
        input_tokens=totals["input_tokens"],
        output_tokens=totals["output_tokens"],
        cache_read_input_tokens=totals["cache_read_input_tokens"],
        cache_creation_input_tokens=totals["cache_creation_input_tokens"],
        total_tokens=sum(totals.values()),
        events=events,
    )
