"""Redaction + payload scrubbing so secrets never reach logs, errors, or the event store.

Pure (no I/O). Two jobs:
  - ``redact_text``: mask token-shaped substrings in free text (for logs / error messages).
  - ``scrub_payload``: recursively scrub a JSON-able value before persistence — mask the
    values of auth-bearing keys and any token-shaped string anywhere inside.

This is how "tokens never leak" (CLAUDE.md) survives an event store (PLAN.md sec 5): nothing is
persisted, logged, or surfaced without passing through here first. Over-redaction is safe;
under-redaction is the danger, so the patterns err toward masking.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "<redacted>"

# Token-shaped material: vendor API keys, OAuth/bearer tokens, AWS keys, JWTs, PEM blocks.
_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"),  # Anthropic
    re.compile(r"sk-[A-Za-z0-9]{16,}"),  # OpenAI-style
    re.compile(r"gh[posru]_[A-Za-z0-9]{16,}"),  # GitHub tokens
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),  # Slack tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"),  # JWT
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{16,}"),  # Authorization: Bearer ...
)

# Keys whose values are auth-bearing regardless of shape — masked wholesale.
_SENSITIVE_KEY = re.compile(
    r"(?i)(authorization|cookie|set-cookie|token|secret|password|passwd|api[_-]?key|"
    r"access[_-]?key|refresh[_-]?token|client[_-]?secret|session)"
)


def redact_text(value: str) -> str:
    """Mask any token-shaped substrings in free text (safe for logs and error messages)."""
    out = value
    for pat in _TOKEN_PATTERNS:
        out = pat.sub(REDACTED, out)
    return out


def scrub_payload(value: Any) -> Any:
    """Recursively scrub a JSON-able value for safe persistence.

    A dict value under an auth-bearing key is masked wholesale; every string is run through
    ``redact_text``; lists and dicts are scrubbed element-wise; other scalars pass through.
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and _SENSITIVE_KEY.search(k):
                out[k] = REDACTED
            else:
                out[k] = scrub_payload(v)
        return out
    if isinstance(value, list):
        return [scrub_payload(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
