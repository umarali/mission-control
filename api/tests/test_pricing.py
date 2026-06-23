"""Tests for the pure consumed-cost pricing (rate-card matching + cost math)."""

from __future__ import annotations

from missioncontrol.pricing import cost_usd, rate_card_for


def test_rate_card_matches_each_family() -> None:
    assert rate_card_for("claude-opus-4-8").input == 5.0  # type: ignore[union-attr]
    assert rate_card_for("claude-sonnet-4-6").output == 15.0  # type: ignore[union-attr]
    assert rate_card_for("claude-haiku-4-5").input == 1.0  # type: ignore[union-attr]
    assert rate_card_for("claude-fable-5").output == 50.0  # type: ignore[union-attr]


def test_rate_card_derived_cache_rates() -> None:
    opus = rate_card_for("claude-opus-4-8")
    assert opus is not None
    assert opus.cache_read == 0.5  # 0.1 × 5
    assert opus.cache_write == 6.25  # 1.25 × 5


def test_rate_card_unknown_and_empty() -> None:
    assert rate_card_for("gpt-5") is None
    assert rate_card_for(None) is None
    assert rate_card_for("") is None


def test_cost_usd_sums_priced_fields() -> None:
    # 1M input @ $5 + 1M output @ $25 + 1M cache_read @ $0.5 + 1M cache_write @ $6.25 = $36.75
    cost = cost_usd(
        model="claude-opus-4-8",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
    )
    assert cost == 36.75


def test_cost_usd_none_for_unpriced_model() -> None:
    assert (
        cost_usd(
            model="gpt-5",
            input_tokens=1_000_000,
            output_tokens=0,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )
        is None
    )
