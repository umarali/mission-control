"""Pure transcript rendering: agent JSONL records -> a normalized, readable list of turns.

Credential-free, no I/O. Tolerant of schema drift (CLAUDE.md C5): unknown blocks/types are
skipped, never fatal. Every visible text is run through ``redact_text`` so a transcript that
happens to contain a pasted token can never leak to the browser (tokens never leak).

A "turn" is what a reader cares about: who spoke, what they said, and which tools fired.
Reasoning/thinking blocks are intentionally excluded to keep the reading view roomy.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import Turn
from .redact import redact_text

DEFAULT_LIMIT = 200

_TEXT_BLOCKS = ("text", "input_text", "output_text")


def _text_and_tools(content: Any) -> tuple[str, list[str]]:
    """Extract (joined visible text, tool names) from a Claude/Codex content value."""
    if isinstance(content, str):
        return content, []
    texts: list[str] = []
    tools: list[str] = []
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype in _TEXT_BLOCKS:
                t = block.get("text")
                if isinstance(t, str) and t:
                    texts.append(t)
            elif btype == "tool_use":
                name = block.get("name")
                if isinstance(name, str):
                    tools.append(name)
            elif btype == "tool_result":
                inner, _ = _text_and_tools(block.get("content"))
                if inner:
                    texts.append(inner)
            # "thinking" / "reasoning" and any unknown block type: skipped on purpose.
    return "\n".join(texts), tools


def _ts(obj: dict[str, Any]) -> str | None:
    ts = obj.get("timestamp")
    return ts if isinstance(ts, str) else None


def render_claude_transcript(
    records: Iterable[dict[str, Any]], *, limit: int = DEFAULT_LIMIT
) -> list[Turn]:
    """Render a Claude transcript (~/.claude/projects/**/*.jsonl) into turns."""
    turns: list[Turn] = []
    for obj in records:
        if not isinstance(obj, dict):
            continue
        msg = obj.get("message")
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        top = obj.get("type")
        if not isinstance(role, str):
            role = top if isinstance(top, str) else "unknown"
        text, tools = _text_and_tools(msg.get("content"))
        if not text and not tools:
            continue
        turns.append(Turn(role=role, text=redact_text(text), tools=tools, ts=_ts(obj)))
    return turns[-limit:]


def render_codex_transcript(
    records: Iterable[dict[str, Any]], *, limit: int = DEFAULT_LIMIT
) -> list[Turn]:
    """Render a Codex rollout (~/.codex/sessions/**/rollout-*.jsonl) into turns."""
    turns: list[Turn] = []
    for obj in records:
        if not isinstance(obj, dict):
            continue
        payload = obj.get("payload")
        payload = payload if isinstance(payload, dict) else obj
        ptype = payload.get("type")
        ts = _ts(obj)
        if ptype == "message":
            role = payload.get("role")
            role = role if isinstance(role, str) else "unknown"
            text, tools = _text_and_tools(payload.get("content"))
            if text or tools:
                turns.append(Turn(role=role, text=redact_text(text), tools=tools, ts=ts))
        elif ptype == "function_call":
            name = payload.get("name")
            if isinstance(name, str):
                turns.append(Turn(role="assistant", text="", tools=[name], ts=ts))
        # function_call_output / reasoning / token_count: skipped for the reading view.
    return turns[-limit:]


def render_transcript(
    agent: str, records: Iterable[dict[str, Any]], *, limit: int = DEFAULT_LIMIT
) -> list[Turn]:
    """Vendor-neutral dispatch by agent name."""
    if agent == "claude":
        return render_claude_transcript(records, limit=limit)
    return render_codex_transcript(records, limit=limit)
