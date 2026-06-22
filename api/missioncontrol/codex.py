"""Pure parser: Codex remaining-window quota from rollout `token_count.rate_limits` records.

Credential-free. Input is already-parsed JSON objects; this module does no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import CodexQuota, Window

_LABELS = {300: "5h", 10080: "weekly"}


def _label(window_minutes: int | None) -> str:
    if window_minutes is None:
        return "unknown"
    return _LABELS.get(window_minutes, f"{window_minutes}min")


def _window(raw: dict[str, Any]) -> Window:
    wm = raw.get("window_minutes")
    wm_int = wm if isinstance(wm, int) else None
    used = raw.get("used_percent")
    used_f = float(used) if isinstance(used, (int, float)) else None
    remaining = None if used_f is None else round(100.0 - used_f, 1)
    resets = raw.get("resets_at")
    blocked = bool(raw.get("rate_limit_reached_type")) or (
        remaining is not None and remaining <= 0
    )
    return Window(
        window=_label(wm_int),
        window_minutes=wm_int,
        remaining_pct=remaining,
        used_pct=used_f,
        resets_at=resets if isinstance(resets, int) else None,
        blocked=blocked,
        stale=False,
    )


def parse_codex_quota(records: Iterable[dict[str, Any]]) -> CodexQuota:
    """Return the most recent rate-limit windows found in a Codex session's records."""
    last_rl: dict[str, Any] | None = None
    for obj in records:
        payload = obj.get("payload")
        payload = payload if isinstance(payload, dict) else obj
        if payload.get("type") == "token_count":
            rl = payload.get("rate_limits")
            if isinstance(rl, dict):
                last_rl = rl

    if last_rl is None:
        return CodexQuota(available=False, degraded="no token_count rate_limits in session")

    windows: list[Window] = []
    for key in ("primary", "secondary"):
        raw = last_rl.get(key)
        if isinstance(raw, dict):
            windows.append(_window(raw))

    if not windows:
        return CodexQuota(available=False, degraded="rate_limits had no usable windows")
    return CodexQuota(available=True, windows=windows)
