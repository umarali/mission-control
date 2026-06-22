# Mission Control (Radar)

Internal, local-first dashboard that shows **remaining rate-limit quota per window** for
**Claude Code** and **OpenAI Codex** side by side (5-hour + weekly), so you can maximize your
usage and stop getting surprised by throttling. Read-only. No agent control.

> Status: planning → v1 build. Full design (Codex-reviewed v3.4) lives in [PLAN.md](PLAN.md).

## v1 scope (quota-only, read-only)

- Four live gauges: Claude 5h / weekly, Codex 5h / weekly — **remaining % + reset countdown**.
- Unused-headroom nudges, throttle warnings, and cross-agent visibility (route the next job to
  whichever agent has room).
- Built from scratch on **Bun built-ins**, near-zero third-party dependencies.
- Reads the vendors' own numbers; **never spends quota to measure quota**; tokens never leak.

## Principles

Vendor-neutral (both agents equal) · local-first · read-only / non-invasive · minimal, audited,
pinned dependencies · tokens never persisted, logged, or sent to the browser.

## First step

The half-day spike: prove the Claude Keychain quota path (the only real risk), then wire Codex.
See [PLAN.md](PLAN.md) §10 and the issues labeled `spike`.

## Roadmap

v1 quota panel → v1.5 agent watch-feed + consumed-cost metering + jump-to-agent → v2
collaboration surfaces (Slack first) + Vercel → later work-threads, shaping hooks, AWS cost watch.
