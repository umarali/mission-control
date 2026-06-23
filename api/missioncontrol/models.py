"""Plain dataclasses for the quota/usage shapes. Framework-free so the collectors stay pure."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    estimated_cost_usd: float | None = None  # estimate from token counts × dated rate card
    pricing_as_of: str | None = None  # date of the rate card used (None when unpriced)


@dataclass
class Turn:
    """One normalized turn in a rendered agent transcript (vendor-neutral reading view)."""

    role: str  # "user" | "assistant" | "tool" | "system" | "unknown"
    text: str  # visible text (redacted; thinking/reasoning excluded)
    tools: list[str] = field(default_factory=list)  # tool names invoked in this turn
    ts: str | None = None  # original timestamp string (ISO), if present


@dataclass
class Transcript:
    """A rendered, read-only transcript for one agent session."""

    available: bool
    agent: str  # "claude" | "codex"
    turns: list[Turn] = field(default_factory=list)
    session_id: str | None = None
    degraded: str | None = None


@dataclass
class Alert:
    """A derived, actionable signal about a quota window (throttle risk or unused headroom)."""

    kind: str  # "throttle" | "headroom"
    surface: str  # "codex" | "claude" | ...
    window: str  # window label, e.g. "5h" | "weekly"
    severity: str  # "warn" | "crit"
    message: str
    remaining_pct: float | None
    resets_at: int | None  # unix epoch seconds


@dataclass
class SlackItem:
    """One normalized 'buried item' from Slack — a mention or a DM worth surfacing.

    Vendor-neutral and credential-free: built from a read-only Slack Web API response, with text
    already run through ``redact_text``. ``slack_ts`` is the original message ts (a stable
    idempotency key so the same message is never stored twice).
    """

    kind: str  # "mention" | "dm"
    channel: str  # channel name (e.g. "general") or "direct message"
    channel_id: str | None
    author: str  # display name if resolvable, else the Slack user id
    text: str  # visible text (redacted)
    ts: float | None  # epoch seconds parsed from the Slack ts string
    slack_ts: str | None  # original Slack ts string ("1718…000200")
    permalink: str | None


@dataclass
class SlackFeed:
    """A read-only feed of Slack buried items (mentions + DMs)."""

    available: bool
    items: list[SlackItem] = field(default_factory=list)
    degraded: str | None = None


@dataclass
class Event:
    """One append-only, normalized event row for the local store (PLAN.md §5).

    ``work_thread_id`` is nullable so the work-thread entity (v3) can land with no migration.
    ``payload`` is always scrubbed before it reaches here, so the store never holds a secret.
    """

    surface: str  # "codex" | "claude" | "slack" | ...
    source: str  # collector/integration name, e.g. "codex.rollout"
    type: str  # "quota.snapshot" | "collector.status" | "alert.throttle" | ...
    ts: int  # unix epoch seconds
    severity: str  # "info" | "warn" | "crit"
    session_id: str | None = None
    work_thread_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    id: int | None = None  # assigned by the store on insert
