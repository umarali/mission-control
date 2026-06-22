# Mission Control — Plan (v4.1)

**Status:** Reframed + stack locked. **Product = Mission Control** (a local-first command center
over the whole dev stack + AI agents). **v1 beachhead = the cross-agent quota panel** (not the
product's identity). **Stack = Next.js + TypeScript (`web/`) + Python/FastAPI (`api/`).** Codex verdict on v4.0: "ship
as the v1 plan"; **v4.1** folds in its P1 refinements (event-store scope + scrub, SSE topology,
spike backoff).
**Date:** 2026-06-22
**Owner:** Umar Ali
**Type:** Internal tool. Solo dev / small team. Built to be useful fast.

**Revision trail:** v1–v2.1 (AWS radar, Codex "ship") → owner tabled AWS, added quota → v3–v3.4
(quota path Codex-reviewed "ship") → **v4.0** (reframed as the Mission Control product with quota
as the v1 beachhead; stack pivoted to Next.js/TS + Python/FastAPI). Quota mechanism details below
are unchanged from the v3.4 Codex review; the architecture and framing are new.

---

## 1. The product (the vision)

**Mission Control** is a local-first command center that gives you one place to **watch** the
significant activity across your entire dev stack and AI agents, and to **act** on it without
tab-hopping or living inside cramped IDE panels.

**Surfaces:** Slack, Asana, GitHub, Google Drive, Vercel, AWS, Claude Code, OpenAI Codex.

**Two views:**
- **Timeline** — ambient awareness, "what just happened" across everything, chronologically.
- **Work-threads** — per-piece-of-work context: one thread bundling the agent session(s) + GitHub
  PR + Asana task + Drive briefs/docs + spend + Slack thread, with auto-captured artifacts.

**Watch / act posture:** watch broadly; **act** on the collaboration surfaces (Slack/Asana/GitHub/
Drive/Vercel) and on notifications; **agents and AWS are watch-only** (no agent control, no infra
mutation). Jump-to-agent hands off to the CLI.

This is the destination. The rest of this plan is how we get there without boiling the ocean.

## 2. Why quota is v1 (the beachhead, not the identity)

This is way more than a quota dashboard. But you build a command center one surface at a time, and
the **cross-agent quota panel** is the right first slice:

1. **Highest daily ROI you feel immediately** — stop wasting use-it-or-lose-it Claude/Codex windows
   and stop getting throttled mid-task.
2. **Lowest risk, fastest to ship** — two read-only collectors + a small UI; no OAuth dance, no
   write actions, no infra.
3. **It builds the pipeline everything else reuses** — reading agent state locally, the normalized
   event store, the live (SSE) UI, the security model for tokens. The watch-feed, work-threads, and
   the SaaS integrations all sit on top of this same spine.

So quota is the wedge; **the product is Mission Control.** The roadmap (§8) is the climb from this
beachhead to the full command center.

## 3. The pains it solves (full product)

1. **Can't see remaining agent allowance** → waste quota or hit limits. (v1 solves this.)
2. **Agents do costly/risky things caught too late** (e.g. a GPU left billing). (AWS watch, later.)
3. **Important Slack / Asana / GitHub items get buried.** (Notification triage, v2.)
4. **Lose the thread on what an agent was doing across sessions.** (Watch-feed + work-threads.)
5. **(Biggest) Context-switching so heavy you can't tell what state anything is in.** (The whole
   point of Mission Control; addressed cumulatively across the roadmap.)

## 4. Principles (non-negotiable)

- **Vendor-neutral.** Claude and Codex are equal citizens; no path first-classes one.
- **Local-first.** Runs on your machine, binds `127.0.0.1`, no public ingress.
- **Read-only / non-invasive.** Never spends quota to measure quota, never mutates infra, never
  changes how agents behave. v1 has no HTTP action endpoint. Act-surfaces arrive deliberately later.
- **Lean + audited dependencies.** Mainstream, maintained, pinned, lockfiled, audited; no
  unmaintained forks or sprawling libraries. (Relaxed from "near-zero" to fit Next.js/FastAPI.)
- **Tokens never leak.** Read at call time, in memory only; never persisted, logged, or sent to the
  browser; redacted from errors.
- **Read the vendor's number, never guess.** Server-authoritative percentages; never hardcode caps.
- **Degrade, never lie.** Parse/auth/stale errors render a clear degraded/stale state, never a blank
  or a wrong number.

## 5. Stack & architecture

```
web/      Next.js (App Router) + TypeScript  — UI, gauges, timeline, work-threads      (pnpm)
api/      Python + FastAPI                    — collectors, integrations, event store, SSE (uv)
PLAN.md   design source of truth
.claude/  agent config (rules, hooks, commands, skills)
```

- **Frontend:** Next.js (App Router) + TypeScript (strict), pnpm. ESLint + Prettier, Vitest.
  Consumes the FastAPI backend over HTTP + SSE. (Next's own server features stay light; the Python
  backend is the brain.)
- **Backend:** Python 3.12+, FastAPI, **uv** (uv.lock committed). **Ruff** (lint+format), **mypy**,
  **pytest**. `httpx` for read-only vendor calls; stdlib `sqlite3` / `aiosqlite` for the event store;
  SSE (and WebSocket later) for live updates. Lean dependency list.
- **Event store:** one local SQLite DB (WAL mode, simple migrations, a retention cap), append-only
  normalized rows `{id, surface, source, session_id, work_thread_id NULLABLE, type, ts, severity,
  payload, ...}`. The nullable `work_thread_id` lets the work-thread entity land later with no
  migration. **In v1 the only rows are quota snapshots, collector status, and alerts** — the
  Timeline is NOT built early. **`payload` is scrubbed before persistence: never store tokens, auth
  headers, or auth-bearing errors** (this is how "tokens never leak" survives an event store).
- **SSE topology:** the browser subscribes **directly to the FastAPI SSE endpoint on `127.0.0.1`**
  with a strict Origin/CORS allowlist. Do not proxy SSE through Next (buffering/runtime hazards).
- **Dev/run:** one command brings up both runtimes (`/dev`), with **pinned Node and Python
  versions** and a health check each; everything binds `127.0.0.1`.
- **Collectors** (`api/`): pure, tolerant, unit-tested functions. v1 ships the Claude + Codex quota
  collectors; v2 adds SaaS integration collectors behind the same interface.
- Bind `127.0.0.1` only. Read endpoints only in v1.

## 6. v1 quota mechanism (verified on this machine; Codex-reviewed)

- **Codex: exact, on disk.** `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` → last `token_count`
  event → `payload.rate_limits` → `primary` (`window_minutes:300`=5h) + `secondary`
  (`window_minutes:10080`=weekly): `used_percent`, `resets_at`. `remaining = 100 - used_percent`.
  Mark stale after `resets_at` until a new event; refresh via `codex app-server`
  `account/rateLimits/read` when available. Label windows by `window_minutes`, never position.
- **Claude: read-only OAuth endpoint.** OAuth token from the **macOS Keychain via `/usr/bin/security`**
  → `GET https://api.anthropic.com/api/oauth/usage` (`anthropic-beta: oauth-2025-04-20`) →
  `utilization` + `resets_at` for `five_hour`/`seven_day`. `remaining = (1-utilization)*100`.
  **No quota-spending probe.** On failure → degraded gauge. Undocumented endpoint + subscription
  token = gray area, consciously accepted for an internal tool; read-only; degrades cleanly.
- **Do NOT use for remaining:** transcript `message.usage`, OTEL counters, Admin API (consumed-only).
- **Token / subprocess safety:** spawn `/usr/bin/security` by absolute path + fixed argv (no shell);
  token in memory only; scrub output; redact from logs/errors; locked/denied Keychain → degraded auth.

## 7. v1 scope & caveats

**In v1 (quota beachhead, read-only):** Claude + Codex quota collectors; four gauges (Claude 5h/
weekly, Codex 5h/weekly) with remaining % + reset countdown; maximize-usage UX (headroom nudge,
throttle warning, cross-agent visibility); out-of-tab OS notifications; the event-store spine;
token/subprocess/localhost security; degraded/stale states.

**Caveats:** C1 Claude quota is a gray-area dependency (accepted). C2 Codex quota can read stale
right after reset (marked). C3 private formats/endpoints break on CLI updates (tolerate + degrade).
C4 Keychain via `security` is a subprocess (accepted; hardened). C5 Keychain ACL/prompt under a
non-signed interpreter may differ (acceptable internal).

**Not in v1:** the watch-feed, consumed-cost metering, jump-to-agent (command-exec) → v1.5; SaaS
integrations + actions → v2; work-threads + AWS → later.

## 8. Roadmap (beachhead → full Mission Control)

- **v1 — Quota beachhead.** The four-gauge cross-agent quota panel + the event-store spine. (This plan.)
- **v1.5 — Agent watch-feed.** Read-only rendered transcripts + consumed token/cost metering +
  jump-to-agent (first command-exec surface; stricter localhost hardening lands here).
- **v2 — Collaboration surfaces + the Timeline.** Slack (first, for the buried-items pain), then
  Asana, GitHub, Drive, Vercel — watch + act behind a guarded action endpoint. The unified Timeline
  becomes real once multiple surfaces feed it.
- **v3 — Work-threads.** Promote the work-thread to a first-class entity with 3-leg artifact linking
  (auto-capture from the tool stream, by-convention, manual). This is the "lose the thread" cure.
- **later — AWS read-only cost/idle watch** (closes pain #2), opt-in pre-prompt shaping hooks.

## 9. First spike (do this before anything else)

About a day, throwaway. The riskiest bet is the **Claude quota path**, so prove it first.

1. **Claude (the risk).** Token from Keychain via `/usr/bin/security find-generic-password -w`
   (discover the service/account name; absolute path + fixed argv, no shell, scrub output), then
   read-only `GET /api/oauth/usage`. Print remaining % + reset for `five_hour`/`seven_day`. No probe.
   Use a short HTTP timeout (~5s) and exponential backoff on 429/5xx with a retry cap. Verify clean
   degraded states on denied/locked Keychain and on 4xx/5xx; token never in args/logs.
2. **Codex.** Parse newest rollout JSONL last `token_count` `rate_limits`; print remaining + reset
   for `primary`/`secondary`; flag stale-after-reset.

**Success:** four real numbers; no token persisted/logged; degraded states work; 429/backoff on the
Claude endpoint. Retires the only real risk; the rest is build.

## 10. Market position

The agent-quota niche is small and split (claumon = Claude-only web; CodexBar = both agents, native
menu-bar; ccusage/clawmetry = consumed-only). We build the quota slice from scratch (lean, audited).
But the **product** is not in that niche: no one ships a neutral, local-first command center that
fuses agent state with collaboration, infra, and storage surfaces into one watch/act pane. That
fusion (and the parked AWS/infra corner) is the durable differentiation; quota is just how we land.

## 11. Open questions

- Caveats C1–C5: accepted by the owner (see §7); revisit only if a vendor changes terms.
- Form factor: web tab vs a menu-bar companion for the always-glanceable gauges (not exclusive).
- Alert channel beyond local OS notification (Slack/push) — when.
- v2 surface order after Slack.

**Resolved:** product = Mission Control (quota = v1 beachhead); stack = Next.js/TS + Python/FastAPI;
Claude quota = read-only `/api/oauth/usage` via Keychain `security` binary, no probe; v1 read-only,
no command-exec surface.

## 12. Success criteria

**v1:** four live gauges show remaining quota + reset for both agents from the vendors' own numbers,
without spending quota; you see which agent has headroom and route accordingly; you stop wasting
quota and getting throttled; token never persisted/logged/exposed; degraded/stale never lies.
**Product:** one place that answers "what is the state of everything" so context-switching stops
costing you the day.
