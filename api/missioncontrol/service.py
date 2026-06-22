"""Wire the filesystem seam to the pure parsers and produce a JSON-able snapshot.

Thin glue (excluded from unit-coverage); the logic it calls is fully tested.
"""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from .claude import parse_claude_consumed
from .codex import parse_codex_quota
from .models import ClaudeConsumed, CodexQuota
from .paths import newest_claude_transcript, newest_codex_rollout, read_jsonl


def snapshot() -> dict[str, Any]:
    """Read both agents' newest local files and return the current quota/usage snapshot."""
    codex_path = newest_codex_rollout()
    if codex_path is not None:
        codex = parse_codex_quota(read_jsonl(codex_path))
    else:
        codex = CodexQuota(available=False, degraded="no Codex sessions found")

    claude_path = newest_claude_transcript()
    if claude_path is not None:
        claude = parse_claude_consumed(read_jsonl(claude_path))
    else:
        claude = ClaudeConsumed(
            available=False,
            input_tokens=0,
            output_tokens=0,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            total_tokens=0,
            events=0,
            degraded="no Claude transcripts found",
        )

    return {
        "generated_at": int(time.time()),
        "codex": asdict(codex),
        "claude": asdict(claude),
    }
