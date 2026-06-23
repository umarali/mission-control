"""Pure parser: Claude remaining-window quota from the OAuth usage endpoint (PLAN.md §6).

Credential-free + no I/O: the input is the already-parsed JSON from GET /api/oauth/usage; the
credentialed fetch lives in the isolated reader seam (claudecreds.py). Server-authoritative:
``remaining = (1 - utilization) * 100`` — never a hardcoded cap. Reuses ``Window`` so Claude
renders with the same gauge as Codex (vendor-neutral). Tolerant: odd/empty shapes degrade.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import ClaudeQuota, Window

# The endpoint's window keys -> (gauge label, window length in minutes). Labelled by meaning,
# never by position. A model-specific weekly window (if present) is left out of the two gauges.
_WINDOWS: dict[str, tuple[str, int]] = {
    "five_hour": ("5h", 300),
    "seven_day": ("weekly", 10080),
}


def _fraction(util: Any) -> float | None:
    """Utilization as a 0..1 fraction. Tolerate a percent (e.g. 36) as well as a fraction (0.36)."""
    if not isinstance(util, (int, float)) or isinstance(util, bool):
        return None
    f = float(util)
    if f > 1.0:  # the API gave a percentage, not a fraction
        f = f / 100.0
    return max(0.0, min(1.0, f))


def _epoch(value: Any) -> int | None:
    """resets_at as a unix epoch. Accept an int/float epoch or an ISO-8601 string; else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
        except ValueError:
            return None
    return None


def parse_claude_quota(usage: Any, *, now: int | None = None) -> ClaudeQuota:
    """Return Claude's remaining-window quota from a usage response. Degrades, never guesses."""
    if not isinstance(usage, dict):
        return ClaudeQuota(available=False, degraded="usage response was not an object")

    windows: list[Window] = []
    for key, (label, minutes) in _WINDOWS.items():
        raw = usage.get(key)
        if not isinstance(raw, dict):
            continue
        frac = _fraction(raw.get("utilization"))
        if frac is None:
            continue
        remaining = round((1.0 - frac) * 100.0, 1)
        resets_at = _epoch(raw.get("resets_at"))
        stale = now is not None and resets_at is not None and resets_at < now
        windows.append(
            Window(
                window=label,
                window_minutes=minutes,
                remaining_pct=remaining,
                used_pct=round(frac * 100.0, 1),
                resets_at=resets_at,
                blocked=remaining <= 0,
                stale=stale,
            )
        )

    if not windows:
        return ClaudeQuota(available=False, degraded="no usable usage windows")
    return ClaudeQuota(available=True, windows=windows)
