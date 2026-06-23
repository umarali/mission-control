"""Pure consumed-cost pricing for Claude usage (PLAN.md §8 — v1.5 cost metering).

Cost here is an explicit ESTIMATE: there is no local server-authoritative cost number, so we
derive it from token counts × a published, dated rate card. Rates are per 1M tokens (USD),
from Anthropic's public pricing, captured on PRICING_AS_OF via the claude-api reference. They
are deliberately easy to update — one table, one date.

Cache reads are priced at 0.1× input; cache writes at the 5-minute-TTL rate (1.25× input, the
default and dominant case) — documented so a reader knows the assumption.

Vendor-neutral by construction: an agent whose model has no rate card yields cost = None
(degraded), exactly like Codex consumed-cost in v1 (no local OpenAI rate source). The cost is
always surfaced as an estimate, never as a billed figure (degrade, never lie).
"""

from __future__ import annotations

from dataclasses import dataclass

PRICING_AS_OF = "2026-06-23"


@dataclass(frozen=True)
class RateCard:
    """Per-1M-token USD rates for one model family."""

    input: float
    output: float
    cache_read: float  # 0.1× input
    cache_write: float  # 5-minute TTL: 1.25× input


def _card(input_: float, output: float) -> RateCard:
    return RateCard(
        input=input_,
        output=output,
        cache_read=round(input_ * 0.1, 4),
        cache_write=round(input_ * 1.25, 4),
    )


# Matched by substring against the transcript's `message.model`. Order is not significant —
# the families are disjoint — but most-specific (fable) is listed first for clarity.
_RATE_CARDS: tuple[tuple[str, RateCard], ...] = (
    ("claude-fable", _card(10.0, 50.0)),
    ("claude-opus", _card(5.0, 25.0)),
    ("claude-sonnet", _card(3.0, 15.0)),
    ("claude-haiku", _card(1.0, 5.0)),
)


def rate_card_for(model: str | None) -> RateCard | None:
    """Return the rate card whose family matches the model id, or None if unknown."""
    if not model:
        return None
    for needle, card in _RATE_CARDS:
        if needle in model:
            return card
    return None


def cost_usd(
    *,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int,
    cache_creation_input_tokens: int,
) -> float | None:
    """Estimated USD cost for one model's token totals, or None if the model is unpriced."""
    card = rate_card_for(model)
    if card is None:
        return None
    per_million = (
        input_tokens * card.input
        + output_tokens * card.output
        + cache_read_input_tokens * card.cache_read
        + cache_creation_input_tokens * card.cache_write
    )
    return round(per_million / 1_000_000, 6)
