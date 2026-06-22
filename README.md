# Mission Control (Radar)

**Mission Control** is a **local-first command center** for your dev stack and AI agents: one place
to **watch** (and act on) the significant activity across Slack, Asana, GitHub, Google Drive,
Vercel, AWS, and your two coding agents (**Claude Code + OpenAI Codex**), instead of tab-hopping
across a dozen tools and cramped IDE panels.

> Status: building **v1**. Full design (Codex-reviewed): [PLAN.md](PLAN.md) (v4.0).

## Where this goes (the product)

- **Timeline** — what just happened across everything, in one chronological feed.
- **Work-threads** — each piece of work with its agent sessions, PRs, tasks, docs, and spend bundled.
- **Watch + act** on Slack / Asana / GitHub / Drive / Vercel; **agents and AWS are watch-only**.

You build a command center one surface at a time. Here is the first one.

## v1: the quota beachhead

The **cross-agent quota panel** — the highest daily-ROI, lowest-risk first slice, and it builds the
agent-data pipeline (local reads, event store, live UI, token security) that everything else reuses.

Four live gauges — **Claude 5h / weekly, Codex 5h / weekly** — each showing **remaining % + reset
countdown**, with headroom nudges so you stop wasting use-it-or-lose-it quota and stop getting
throttled mid-task. Reads the vendors' own numbers, **never spends quota to measure quota**.
Read-only, no agent control.

## Principles

Vendor-neutral (both agents equal) · local-first (binds 127.0.0.1) · read-only / non-invasive ·
lean + audited + pinned dependencies · tokens never persisted, logged, or sent to the browser ·
degrade, never lie.

## Stack

- `web/` — Next.js (App Router) + TypeScript (pnpm)
- `api/` — Python + FastAPI (uv, Ruff, mypy, pytest); SQLite event store; SSE for live updates

## Roadmap

v1 quota beachhead → v1.5 agent watch-feed + consumed-cost metering → v2 collaboration surfaces
(Slack first) + Vercel + the unified Timeline → v3 work-threads + artifact linking → later AWS
cost/idle watch + opt-in shaping hooks.

## First step

The half-day spike: prove the Claude Keychain quota path (the only real risk), then wire Codex.
See [PLAN.md](PLAN.md) §9 and the `spike` issues. Run `/spike` to execute it.
