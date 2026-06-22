"""Plain dataclasses for the quota/usage shapes. Framework-free so the collectors stay pure."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Window:
    """One rate-limit window for an agent (e.g. Codex 5h / weekly)."""

    window: str  # "5h" | "weekly" | "<n>min" | "unknown"
    window_minutes: int | None
    remaining_pct: float | None
    used_pct: float | None
    resets_at: int | None  # unix epoch seconds
    blocked: bool
    stale: bool


@dataclass
class CodexQuota:
    """Codex remaining-window quota, read credential-free from the rollout file."""

    available: bool
    windows: list[Window] = field(default_factory=list)
    degraded: str | None = None


@dataclass
class ClaudeConsumed:
    """Claude consumed-token totals, read credential-free from the transcript file."""

    available: bool
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    total_tokens: int
    events: int
    degraded: str | None = None
