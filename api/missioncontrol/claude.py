"""Pure parser: Claude consumed-token totals from transcript `message.usage` records.

Credential-free. Input is already-parsed JSON objects; this module does no I/O. It also computes
a per-model breakdown and an ESTIMATED consumed cost (PLAN.md §8 v1.5) — see pricing.py for the
rate-card caveats. Cost is an estimate, never a billed figure.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import ClaudeConsumed
from .pricing import PRICING_AS_OF, cost_usd

_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def parse_claude_consumed(records: Iterable[dict[str, Any]]) -> ClaudeConsumed:
    """Sum token usage across a Claude transcript's records, with a per-model cost estimate."""
    totals: dict[str, int] = {k: 0 for k in _FIELDS}
    by_model: dict[str, dict[str, int]] = {}
    events = 0
    for obj in records:
        msg = obj.get("message")
        usage = msg.get("usage") if isinstance(msg, dict) else None
        if not isinstance(usage, dict):
            usage = obj.get("usage")
        if not isinstance(usage, dict):
            continue
        events += 1
        raw_model = msg.get("model") if isinstance(msg, dict) else None
        model = raw_model if isinstance(raw_model, str) else "unknown"
        bucket = by_model.setdefault(model, {k: 0 for k in _FIELDS})
        for k in _FIELDS:
            v = usage.get(k)
            if isinstance(v, int) and not isinstance(v, bool):
                totals[k] += v
                bucket[k] += v

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

    cost = 0.0
    priced = False
    for model, b in by_model.items():
        c = cost_usd(
            model=model,
            input_tokens=b["input_tokens"],
            output_tokens=b["output_tokens"],
            cache_read_input_tokens=b["cache_read_input_tokens"],
            cache_creation_input_tokens=b["cache_creation_input_tokens"],
        )
        if c is not None:
            cost += c
            priced = True

    return ClaudeConsumed(
        available=True,
        input_tokens=totals["input_tokens"],
        output_tokens=totals["output_tokens"],
        cache_read_input_tokens=totals["cache_read_input_tokens"],
        cache_creation_input_tokens=totals["cache_creation_input_tokens"],
        total_tokens=sum(totals.values()),
        events=events,
        estimated_cost_usd=round(cost, 6) if priced else None,
        pricing_as_of=PRICING_AS_OF if priced else None,
    )
