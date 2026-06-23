"""Tests for the pure transcript renderers (tolerant parsing + redaction)."""

from __future__ import annotations

from missioncontrol.redact import REDACTED
from missioncontrol.transcript import (
    render_claude_transcript,
    render_codex_transcript,
    render_transcript,
)

LEAK = "sk-ant-" + "A1b2C3d4E5f6G7h8J9k0"


def test_claude_string_content_and_timestamp() -> None:
    recs = [{"type": "user", "message": {"role": "user", "content": "hello"}, "timestamp": "T1"}]
    turns = render_claude_transcript(recs)
    assert len(turns) == 1
    assert turns[0].role == "user" and turns[0].text == "hello" and turns[0].ts == "T1"


def test_claude_block_content_text_tools_and_tool_result() -> None:
    recs = [
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "let me check"},
                    {"type": "thinking", "thinking": "hidden reasoning"},
                    {"type": "tool_use", "name": "Read", "input": {}},
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {"type": "tool_result", "content": [{"type": "text", "text": "file body"}]}
                ],
            },
        },
    ]
    turns = render_claude_transcript(recs)
    assert turns[0].text == "let me check"  # thinking excluded
    assert turns[0].tools == ["Read"]
    assert turns[1].text == "file body"  # tool_result text surfaced


def test_claude_redacts_pasted_token() -> None:
    recs = [{"type": "user", "message": {"role": "user", "content": f"my key is {LEAK}"}}]
    turns = render_claude_transcript(recs)
    assert LEAK not in turns[0].text and REDACTED in turns[0].text


def test_claude_skips_empty_and_non_message_records() -> None:
    recs = [
        {"type": "summary"},  # no message
        {"message": "oops"},  # message not a dict
        {"type": "assistant", "message": {"role": "assistant", "content": []}},  # empty
        "not-a-dict",
    ]
    assert render_claude_transcript(recs) == []  # type: ignore[arg-type]


def test_claude_role_falls_back_to_top_level_type() -> None:
    recs = [{"type": "assistant", "message": {"content": "hi"}}]
    assert render_claude_transcript(recs)[0].role == "assistant"
    recs2 = [{"message": {"content": "hi"}}]
    assert render_claude_transcript(recs2)[0].role == "unknown"


def test_claude_limit_keeps_last_turns() -> None:
    recs = [{"type": "user", "message": {"role": "user", "content": str(i)}} for i in range(5)]
    turns = render_claude_transcript(recs, limit=2)
    assert [t.text for t in turns] == ["3", "4"]


def test_codex_message_and_function_call() -> None:
    recs = [
        {
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "do it"}],
            },
            "timestamp": "T",
        },
        {"payload": {"type": "function_call", "name": "shell", "arguments": "{}"}},
        {"payload": {"type": "reasoning"}},  # skipped
        {"payload": {"type": "token_count"}},  # skipped
    ]
    turns = render_codex_transcript(recs)
    assert [t.role for t in turns] == ["user", "assistant"]
    assert turns[0].text == "do it" and turns[0].ts == "T"
    assert turns[1].tools == ["shell"]


def test_codex_flat_payload_and_unknown_role() -> None:
    recs = [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}]
    turns = render_codex_transcript(recs)
    assert turns[0].role == "unknown" and turns[0].text == "ok"


def test_codex_redacts_and_skips_non_dict() -> None:
    recs = [
        "nope",
        {"payload": {"type": "message", "role": "assistant", "content": f"tok {LEAK}"}},
    ]
    turns = render_codex_transcript(recs)  # type: ignore[arg-type]
    assert len(turns) == 1 and LEAK not in turns[0].text


def test_claude_tolerates_messy_blocks() -> None:
    recs = [
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    "not-a-dict",  # block not a dict -> skipped
                    {"type": "text"},  # text missing -> skipped
                    {"type": "text", "text": ""},  # empty text -> skipped
                    {"type": "tool_use"},  # no name -> skipped
                    {"type": "tool_result", "content": []},  # empty inner -> skipped
                    {"type": "image"},  # unknown block type -> skipped
                    {"type": "text", "text": "kept"},
                ],
            },
        }
    ]
    turns = render_claude_transcript(recs)
    assert turns[0].text == "kept" and turns[0].tools == []


def test_claude_content_none_is_skipped() -> None:
    recs = [{"type": "user", "message": {"role": "user", "content": None}}]
    assert render_claude_transcript(recs) == []


def test_codex_skips_empty_message_nameless_call_and_unknown() -> None:
    recs = [
        {"payload": {"type": "message", "role": "user", "content": []}},  # empty -> skipped
        {"payload": {"type": "function_call"}},  # no name -> skipped
        {"payload": {"type": "totally_unknown"}},  # unrecognized -> skipped
    ]
    assert render_codex_transcript(recs) == []


def test_render_transcript_dispatch() -> None:
    claude = [{"type": "user", "message": {"role": "user", "content": "a"}}]
    codex = [{"payload": {"type": "message", "role": "user", "content": "b"}}]
    assert render_transcript("claude", claude)[0].text == "a"
    assert render_transcript("codex", codex)[0].text == "b"
    assert render_transcript("anything-else", codex)[0].text == "b"  # defaults to codex
