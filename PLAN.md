# Mission Control — Plan (Draft v3.4)

**Status:** DRAFT v3.4 — **Codex verdict: "ship this as the v1 plan"** (pass 6). Built from scratch
on Bun built-ins, near-zero deps (claumon dropped for supply-chain + maintenance reasons).
Quota-only, purely read-only. Final wording + subprocess-hardening notes folded in.
**Date:** 2026-06-21
**Owner:** Umar Ali
**Type:** Internal tool. Solo dev / small team. Built to be useful fast, not (yet) a product to sell.
**Working v1 name:** Radar (agent quota).

**Revision trail:** v1 (revise: AWS kill-switch) → v2.1 (ship) → owner tabled AWS, added quota →
v3 (revise: read-only-violating probe, Keychain/policy) → v3.1 (probe removed, Claude path decided)
→ v3.2 (v1 scoped to quota-only; watch-feed → v1.5) → v3.3 (claumon dropped; build-from-scratch,
minimal audited deps) → **v3.4** (Codex pass 6: ship; wording + subprocess hardening tightened).

---

## 1. Problem

Running Claude Code and Codex hard across many projects (measured: 64 Claude + 12 Codex sessions
in 24h across 32 projects) while living in Slack, Asana, GitHub, Drive, and Vercel, you lose the
ability to see *state*. The pains:

1. **You can't see your remaining agent allowance,** so you either slam into a rate limit
   mid-task or let a 5-hour window reset with quota unused. Both waste your day.
2. **Agents do things you catch too late** (the original case: an agent left a GPU billing).
3. **Important Slack / Asana / GitHub items get buried.**
4. **You lose the thread on what an agent was doing across sessions.**
5. **(Biggest) Context-switching so heavy you can't tell what state anything is in.**

**What v1 explicitly does NOT solve:** cost/idle-resource surprises (pain #2; AWS tabled), and the
lost-thread / context-switching pains (#4, #5) which need the watch-feed (v1.5) and the two views
(later). v1 targets pain #1 head-on and nothing else.

---

## 2. What it is

A **web-based dashboard** to *watch* your agents and dev stack in one place, starting with the
one number you can't see today: how much agent quota you have left, per window, for both agents.

**Surfaces (current scope):** Claude Code, OpenAI Codex (v1, quota only); Slack, Asana, GitHub,
Google Drive, Vercel (v2+). AWS: tabled.

**Two views (longer arc):** Timeline (ambient awareness) and Work-threads (per-piece-of-work
context). **v1 ships only the quota panel** (purely read-only). The agent watch-feed is v1.5; the
two views fill in later.

---

## 3. Principles (non-negotiable)

- **Vendor-neutral.** Both agents are equal citizens. Seeing them side by side is the point.
- **Local-first.** Runs on your machine. No public ingress.
- **Read-only and non-invasive.** Reads only. Never spends quota to measure quota, never runs an
  agent action, never changes how your agents behave. **v1 has no agent/control command execution
  and no HTTP action endpoint;** the only subprocesses are allowlisted first-party OS binaries
  (`/usr/bin/security` for the Keychain, the OS notifier for alerts). No active probes in the normal flow.
- **Minimal, audited dependencies.** Prefer language built-ins and first-party OS tools over
  third-party packages. Every dependency must be actively maintained, pinned, lockfile-committed,
  and audited. After the axios and LiteLLM supply-chain incidents, an unmaintained fork or a heavy
  transitive tree is a liability, not a shortcut. **No dependency we would not read in full.**
- **Tokens never leak.** OAuth/bearer tokens are never persisted by the app, never sent to the
  browser, and are redacted from all logs and crash output.
- **Reading quality is a feature** (applies once the watch-feed lands in v1.5).
- **Watch-only for agents.** Jump-to-agent (`claude --resume` / `codex resume`) arrives with the
  watch-feed in v1.5; it is the first command-exec surface and gets the stricter hardening then.
- **Read the vendor's number, never guess.** Quota comes from server-authoritative percentages,
  never from hardcoded plan caps (Anthropic stopped publishing fixed caps in 2026).

---

## 4. Feature pillars

1. **Cross-agent quota panel (v1 hero).** Four live gauges: Claude 5h, Claude weekly, Codex 5h,
   Codex weekly. Each shows **remaining % + reset countdown**. Framed for *maximizing usage*:
   - an **unused-headroom nudge** ("30 min to reset, 55% untouched, queue work now"),
   - a **throttle warning** when remaining < ~5% or a window is blocked,
   - **cross-agent visibility** so you can see at a glance which agent has room and *choose* to
     send the next job there. (Visibility + nudges, not auto-routing.)
2. **Consumed token/cost metering** per agent / thread / project (v1.5+). Separate from quota
   (different sources). Claude cost `exact`, Codex `estimated`/`unknown`. Never faked.
3. **Agent watch-feed (read-only)** with rendered transcripts + needs-attention flag. **(v1.5.)**
4. **Notification triage + act** (v2) — buried Slack/Asana/GitHub items in one list.
5. **Work-threads + artifact linking** (later) — auto-capture from the tool stream, by-convention, manual.
6. **Opt-in pre-prompt shaping hooks** (later) — agents emit dashboard-ready artifacts. Always optional.

---

## 5. Technical findings (verified on this machine)

**Quota (the v1 core):**
- **Codex: exact, on disk, but freshness-bounded.** Tail newest
  `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`, parse `payload.type == "token_count"`, read
  `payload.rate_limits` → `primary` (`window_minutes:300` = 5h) and `secondary`
  (`window_minutes:10080` = weekly), each `used_percent`/`window_minutes`/`resets_at`.
  `remaining = 100 - used_percent`. **Caveat:** the percent is only as fresh as the last
  `token_count` event, so just after a reset it can read stale. Mark the gauge "as of last
  activity" past `resets_at`, and refresh via `codex app-server` `account/rateLimits/read` when available.
- **Claude: read-only OAuth endpoint (decided).** Read the OAuth token from the macOS Keychain,
  call `GET https://api.anthropic.com/api/oauth/usage` with `anthropic-beta: oauth-2025-04-20`.
  Returns `utilization` (0–1) + `resets_at` for `five_hour` and `seven_day`.
  `remaining = (1-utilization)*100`. **No quota-spending probe.** On 4xx/5xx or auth failure, the
  Claude gauge shows a **degraded** state; it never falls back to anything that consumes quota.
- **Policy note (accepted):** uses your subscription OAuth token against an undocumented endpoint.
  Your own account, read-only, the same call the official CLI makes. Owner has consciously accepted
  this gray area for an internal tool. Revisit if vendor terms change.
- **Do NOT use for remaining:** transcript `message.usage`, OTEL counters, `stats-cache.json`,
  Admin Usage API. Consumed-only (no reset, no server cap).
- **Plan-tier handling:** label windows by `window_minutes`, never field position. This box reads
  Codex `plan_type: prolite`.

**Token / Keychain security:**
- Read the OAuth token from the macOS Keychain via the **first-party `security` binary**
  (`security find-generic-password ... -w`), which adds **zero third-party dependencies**. The
  spike must discover the exact Keychain service/account name Claude Code stores it under.
- **Deliberate tradeoff:** a "scoped Keychain API" would require a third-party native module
  (keytar-style), which conflicts with the dependency-minimalism principle and is itself a
  supply-chain surface. We choose the zero-dep OS binary and mitigate: hold the token only in
  memory, never write it to disk/SQLite, never send it to the browser, scrub it from the
  `security` subprocess output, and redact it from logs and panic traces.
- Handle locked Keychain / denied permission as a **degraded auth** state ("Claude quota
  unavailable, unlock Keychain"), not a retry loop.

---

## 6. Premises and accepted caveats

**Premises (agreed):** the quota panel is the v1 hero and lowest-risk-highest-value piece; v1 is
built from scratch on built-ins (no unmaintained fork, near-zero deps); v1 is purely read-only
with no command-exec surface; polling is adaptive with jitter and respects 429s.

**Accepted caveats:**
- **C1 — Claude quota is a gray-area dependency** (undocumented endpoint + subscription OAuth
  token), accepted consciously. Read-only; degrades cleanly if it ever stops working.
- **C2 — Consumed cost is best-effort for Codex** (relevant only to the v1.5+ dollar-metering pillar).
- **C3 — Codex quota can read stale right after a reset** until a new event lands; marked as such.
- **C4 — Jump-to-agent is a command-exec surface,** so it is deferred to v1.5 and is where the
  stricter localhost hardening first applies.
- **C5 — Private formats/endpoints break on CLI updates.** Tolerate `resets_at` vs
  `resets_in_seconds`, null fields; degrade, never crash.
- **C6 — Keychain via the `security` binary is a subprocess, not a scoped API.** Accepted to keep
  the dependency footprint at zero; mitigated by output scrubbing and never persisting the token.
- **C7 — Keychain ACL/prompt behavior under Bun-as-interpreter may differ from a signed app.**
  Acceptable for an internal v1; expect a possible Keychain access prompt for the `security` call.

---

## 7. Approaches considered

- **A. Build minimal from scratch on Bun built-ins (recommended).** Bun gives a built-in HTTP
  server, built-in SQLite, native `fetch`, and native file-watch, so v1 needs **near-zero
  third-party packages**: no HTTP client (use `fetch`), no DB driver, no web framework, no ws.
  Keychain via the OS `security` binary. The v1 feature surface is tiny (two collectors + four
  gauges), so re-deriving it is cheap and we own and audit every line. Read **claumon / CodexBar /
  codex-ratelimit as references** for the on-disk/endpoint formats; depend on none of them.
  **Effort S–M, risk Low.**
- **B. Fork claumon — rejected.** Unmaintained, and forking means inheriting an un-audited
  transitive tree. The only thing it offered (a working Claude pipeline) is a Keychain read plus
  one GET, trivial to rebuild. Supply-chain trust kills this option.
- **C. Fork CodexBar — reference only.** Native macOS Swift menu-bar app; useful to *read* for the
  Codex `rate_limits` parse, but a third-party codebase in another language, not a base.

---

## 8. Chosen path

**Build minimal from scratch on Bun built-ins (Approach A).** Execution order follows the spike:
**prove Claude first** (the risk), then wire Codex (exact), then the cross-agent UI.

- **v1:** four-gauge cross-agent quota panel + headroom nudges + throttle warnings, built on Bun
  built-ins. **Read-only local/HTTP I/O, no agent/control command execution, no transcript parsing, near-zero deps.**
- **v1.5:** the read-only agent watch-feed (readable transcripts) + consumed token/cost metering +
  jump-to-agent (allowlisted local command). This is where the command-exec surface and its
  stricter localhost hardening first apply.
- **v2:** collaboration surfaces (Slack first) + Vercel + a guarded action endpoint; Slack/push alerts.
- **later:** work-threads + 3-leg artifact linking; opt-in shaping hooks; **un-table AWS** as a
  read-only cost/idle watch (the parked differentiator that closes pain #2).

---

## 9. v1 architecture (quota-only, read-only, near-zero deps)

- **Base:** a single Bun process on `127.0.0.1` using **built-ins only**: built-in HTTP server,
  built-in SQLite, native `fetch`, native file-watch (with a polling fallback). One hand-written
  HTML/vanilla-JS page. `Bun.serve` must explicitly set `hostname: "127.0.0.1"` (it defaults to
  `0.0.0.0`, which would silently break the no-public-ingress promise); the SSE endpoint must
  disable the idle timeout (`server.timeout(req, 0)`). **Dependency budget: zero third-party runtime
  packages as the target; anything added must be maintained, pinned, lockfile-committed, and small
  enough to read in full.**
- **Claude collector:** OS `security` binary → token → read-only `fetch GET /api/oauth/usage` →
  `remaining` + reset for `five_hour` and `seven_day`. No probe. On failure: degraded gauge.
  Adaptive polling ~60s with jitter; respect 429 with backoff.
- **Codex collector:** prefer `account/rateLimits/read` (app-server) when reachable; else file-watch
  newest rollout JSONL last `token_count` `rate_limits`. Emit per window `{window, remaining,
  resets_at, plan_type, blocked, stale}` for `primary`/`secondary`. Poll on change or 30–60s.
- **Render:** four labeled gauges, each "N% left, resets in HH:MM", plan label per agent, red on
  blocked or remaining < ~5%, the headroom nudge, and a **"data degraded / stale"** badge per
  collector on schema/auth/stale error (never a blank or a wrong number).
- **Alerts:** local OS/desktop notification on throttle-warning and unused-headroom nudge (via the
  OS notifier binary, no package).
- **Localhost hardening:** the HTTP surface exposes **only read endpoints (no action endpoint)**, but
  still set an Origin check + CSRF protection + a random per-session token as a baseline, and lock
  down SQLite file perms. The HTTP action surface and its stricter hardening arrive in v1.5.
- **Subprocess hardening:** spawn `/usr/bin/security` and the notifier by **absolute path with a
  fixed argv array, never via a shell**; never pass the token as an argument; cap and scrub captured
  stdout/stderr; redact the token before any error is wrapped or logged; never log the child-process
  object. (Leakage risk is via stdout/crash dumps/logs, not argv.)
- **Storage:** built-in SQLite, append-only event rows with a nullable `work_thread_id` for later.

**Cut from v1:** the agent watch-feed and jump-to-agent (→ v1.5); consumed cost metering (→ v1.5);
Claude per-model weekly, Codex monthly, burn-rate forecasting, historical charts. Four gauges first.

---

## 10. First spike (do this before anything else)

About a day, throwaway. The riskiest bet is the **Claude quota path**, so prove it first.

1. **Claude quota (the risk).** Read the OAuth token from the macOS Keychain via
   `security find-generic-password -w` (discover the service/account name first), call
   `GET /api/oauth/usage` with the beta header, print `remaining %` + reset for `five_hour` and
   `seven_day`. No probe fallback. Spawn `/usr/bin/security` by absolute path with a fixed argv array
   (no shell), scrub its output, and confirm the token never appears in args, logs, or errors. Verify
   it survives a denied/locked Keychain and an unavailable endpoint by entering a clean degraded state.
2. **Codex quota.** Read the newest rollout JSONL's last `token_count` `rate_limits`, print
   remaining + reset for `primary`/`secondary`; verify the stale-after-reset case is flagged.
3. **(v1.5 prep, optional) Tolerant transcript parse.** Only if you want to de-risk the watch-feed
   now: read a large and a partially-written transcript from each agent without crashing.

**Success bar (all required for v1):**
- Four real remaining-% + reset numbers print for both agents.
- The Claude collector reads the **Keychain via the `security` binary** (not a creds file), and
  **no token is persisted or logged** anywhere.
- Degraded states work: Keychain denied, endpoint 4xx/5xx, and Codex-stale-after-reset all show a
  clean degraded/stale badge rather than crashing or showing a wrong number.
- 429/backoff behaves on the Claude endpoint.
- The `security` call is spawned by **absolute path + fixed argv (no shell)**, its output scrubbed,
  and the token never lands in args, logs, or errors.
- **Dependency check:** the spike (and the v1 design it implies) uses **only Bun built-ins + the OS
  `security`/notifier binaries**; any third-party package considered is maintained, pinned, and
  small enough to read in full, with a noted reason.

Passing this retires the Claude access risk, the only thing between us and the v1 hero.

---

## 11. Market position

claumon (Claude-only, web) and CodexBar (both agents, native menu-bar) are useful **references**
for the data formats, but claumon is unmaintained and we depend on neither: v1 is built from
scratch on built-ins. No shipping product is a neutral cross-agent quota pane that grows into a
watch-feed and, later, multi-surface fusion. For an internal tool, owning a tiny audited codebase
is the point. Durable differentiation (multi-surface fusion, the parked AWS/infra watch corner)
returns in v2+.

---

## 12. Open questions

- Confirm caveats C1–C7.
- **Stack:** build from scratch on Bun built-ins (recommended) — confirm, or prefer another
  minimal-dependency runtime?
- **Keychain access:** OS `security` binary (zero-dep, recommended) vs a vetted native module — confirm.
- **Form factor:** web tab vs a menu-bar widget for always-glanceable gauges? (Not mutually exclusive long-term.)
- Alert channel (v1 default local OS notification; pull Slack/push forward?).
- When (if) to un-table AWS as a read-only cost watch.

**Resolved:** Claude quota source = read-only `GET /api/oauth/usage` via Keychain token (read with
the OS `security` binary), no active probe. v1 is **quota-only** (pure read-only, no command-exec
surface). Build base = **from scratch on Bun built-ins**; claumon dropped for supply-chain /
maintenance reasons. Watch-feed, consumed-cost metering, and jump-to-agent are **v1.5**.

---

## 13. Success criteria

- Four live gauges show **remaining quota + reset countdown** for both agents, from the vendors'
  own numbers (no hardcoded caps), and **without spending any quota to read it**.
- You can glance and tell **which agent has headroom** and choose to route the next job there.
- You stop **wasting quota** at window reset and stop getting surprised by throttling mid-task.
- Your OAuth token is **never persisted, logged, or exposed to the browser.**
- The v1 runtime depends on **near-zero third-party packages** (Bun built-ins + OS `security`/
  notifier binaries); the lockfile is committed and every dependency is audited.
- The panel shows a **degraded/stale badge**, never a blank or a wrong number, when a format or
  endpoint changes.
