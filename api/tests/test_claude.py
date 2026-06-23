"""Tests for the pure Claude consumed-tokens parser, including degraded cases."""

from __future__ import annotations

from missioncontrol.claude import parse_claude_consumed


def _msg(usage: dict[str, int]) -> dict[str, object]:
    return {"message": {"usage": usage}}


def _msg_model(model: str, usage: dict[str, int]) -> dict[str, object]:
    return {"message": {"model": model, "usage": usage}}


def test_sums_usage_across_records() -> None:
    records = [
        _msg({"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 1000}),
        _msg({"input_tokens": 200, "output_tokens": 25, "cache_creation_input_tokens": 300}),
    ]
    c = parse_claude_consumed(records)
    assert c.available is True
    assert c.events == 2
    assert c.input_tokens == 300
    assert c.output_tokens == 75
    assert c.cache_read_input_tokens == 1000
    assert c.cache_creation_input_tokens == 300
    assert c.total_tokens == 1675


def test_usage_at_top_level_when_no_message() -> None:
    c = parse_claude_consumed([{"usage": {"input_tokens": 10, "output_tokens": 5}}])
    assert c.available is True
    assert c.total_tokens == 15


def test_message_not_a_dict_falls_back_to_top_level() -> None:
    c = parse_claude_consumed([{"message": "oops", "usage": {"output_tokens": 7}}])
    assert c.available is True
    assert c.output_tokens == 7


def test_non_int_values_are_skipped() -> None:
    c = parse_claude_consumed([_msg({"input_tokens": "lots", "output_tokens": 9})])  # type: ignore[dict-item]
    assert c.input_tokens == 0
    assert c.output_tokens == 9


def test_records_without_usage_are_ignored() -> None:
    c = parse_claude_consumed([{"type": "summary"}, {"message": {"role": "user"}}])
    assert c.available is False
    assert c.degraded is not None
    assert c.total_tokens == 0


def test_estimated_cost_per_model() -> None:
    # 1M output on Opus = $25; 1M output on Sonnet = $15 -> $40 total.
    c = parse_claude_consumed(
        [
            _msg_model("claude-opus-4-8", {"output_tokens": 1_000_000}),
            _msg_model("claude-sonnet-4-6", {"output_tokens": 1_000_000}),
        ]
    )
    assert c.estimated_cost_usd == 40.0
    assert c.pricing_as_of is not None


def test_no_cost_when_model_unpriced() -> None:
    # No model field -> "unknown" -> unpriced -> cost stays None but tokens still sum.
    c = parse_claude_consumed([_msg({"output_tokens": 500})])
    assert c.output_tokens == 500
    assert c.estimated_cost_usd is None
    assert c.pricing_as_of is None
