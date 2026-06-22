"""Filesystem seam: locate + read the agents' local JSONL files. Credential-free.

Kept thin and isolated (and excluded from unit-coverage) so the parsers above stay 100% pure.
Reads ONLY the rollout/transcript files, never any auth/credential file.
"""

from __future__ import annotations

import glob
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def _newest(pattern: str) -> str | None:
    files = [f for f in glob.glob(pattern, recursive=True) if os.path.isfile(f)]
    return max(files, key=os.path.getmtime) if files else None


def newest_codex_rollout(home: Path | None = None) -> str | None:
    base = home or Path.home()
    return _newest(str(base / ".codex/sessions/**/rollout-*.jsonl"))


def newest_claude_transcript(home: Path | None = None) -> str | None:
    base = home or Path.home()
    return _newest(str(base / ".claude/projects/**/*.jsonl"))


def read_jsonl(path: str) -> Iterator[dict[str, Any]]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (ValueError, TypeError):
                continue  # tolerate partial / malformed lines
            if isinstance(obj, dict):
                yield obj
