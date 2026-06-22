# CLAUDE.md — Mission Control (Radar)

Project rules for AI coding agents (Claude Code, Codex) working in this repo. Read this first.

## What this is

A local-first dashboard showing **remaining rate-limit quota per window** for Claude Code and
OpenAI Codex side by side (5h + weekly), so the user can maximize usage and avoid throttling.
Read-only, no agent control. Full design is the source of truth: [PLAN.md](PLAN.md) (v3.4).

## Product principles (do not violate)

These are load-bearing. A change that breaks one is wrong even if it "works".

1. **Read-only / non-invasive.** The app never runs an agent, never mutates the user's infra, and
   never spends quota to measure quota (no `max_tokens:1` probes, no write calls to vendor APIs).
   v1 has no HTTP action endpoint.
2. **Tokens never leak.** OAuth/bearer tokens are read at call time, held in memory only, **never**
   written to disk/DB, **never** sent to the browser, and **redacted** from logs and errors.
3. **Read the vendor's number, never guess.** Quota comes from server-authoritative percentages
   (`utilization` / `used_percent`). Never hardcode plan caps.
4. **Lean, audited dependencies.** Prefer built-ins and first-party tools. Every dependency must be
   actively maintained, pinned, lockfiled, and small enough to read. No unmaintained forks. When
   adding a dependency, justify it in the PR. (Relaxed from "near-zero" to fit Next.js/FastAPI, but
   the discipline holds.)
5. **Vendor-neutral.** Claude and Codex are equal citizens. No code path first-classes one.
6. **Degrade, never lie.** On a parse/auth/stale error, show a clear "degraded / stale" state.
   Never render a blank gauge or a wrong number.

## Tech stack & layout

```
web/          Next.js (App Router) + TypeScript frontend        — pnpm
api/          Python + FastAPI backend (collectors, SSE)        — uv
PLAN.md       design source of truth (Codex-reviewed)
.claude/      agent config: hooks, commands, skills, settings
```

- **Frontend:** Next.js (App Router), TypeScript (strict), pnpm. ESLint + Prettier. Vitest for
  unit, Playwright optional for e2e later.
- **Backend:** Python 3.12+, FastAPI, managed with **uv** (uv.lock committed). **Ruff** for
  lint + format, **mypy** for types, **pytest** for tests. `httpx` for the read-only Claude GET;
  the stdlib `sqlite3` (or `aiosqlite`) for storage. Keep the dependency list short.
- **Collectors** (the heart of v1) live in `api/`: a Claude collector (Keychain token via the OS
  `security` binary → read-only `GET /api/oauth/usage`) and a Codex collector (parse
  `~/.codex/sessions/.../rollout-*.jsonl` `rate_limits`). See PLAN.md §5, §9.
- Bind everything to `127.0.0.1` only. No public ingress.

## Commands

Frontend (`web/`):
- `pnpm dev` — dev server · `pnpm build` — prod build
- `pnpm lint` — ESLint · `pnpm typecheck` — `tsc --noEmit` · `pnpm test` — Vitest

Backend (`api/`):
- `uv run fastapi dev` — dev server (127.0.0.1)
- `uv run ruff check .` / `uv run ruff format .` — lint / format
- `uv run mypy .` — types · `uv run pytest` — tests

Use the `/check` command to run lint + types + tests across both. Use `/dev` to run the stack.

## Conventions

**TypeScript**
- `strict: true`. No `any` without a `// reason:` comment. Prefer `unknown` + narrowing.
- Server logic in route handlers / server components; keep client components thin.
- No secret ever reaches a client component or the network response. Quota numbers only.
- Validate external/JSON data at the boundary (e.g. zod) before trusting its shape.

**Python**
- Full type hints; `mypy` clean. `ruff` clean (it is both linter and formatter here).
- `async` for I/O (httpx, file reads). Small, pure functions for parsing; test them directly.
- Subprocess rule (critical): spawn `/usr/bin/security` and any OS binary by **absolute path with
  a fixed argv list, never `shell=True`**. Never pass a token as an argument. Cap and scrub
  captured output. Redact before raising/logging. See PLAN.md §9 "Subprocess hardening".

**Both**
- Small PRs, one concern each. Match the surrounding style. No drive-by reformatting.
- Tolerant parsers for the private CLI formats: handle schema drift, partial writes, null fields,
  and file rollover; surface a degraded state instead of crashing (PLAN.md C5).

## Security (this is a PUBLIC repo)

- **Never commit secrets.** Tokens live in the OS Keychain and are read at runtime. A PreToolUse
  hook blocks writing `.env`/secret files and pasting token-shaped strings; do not work around it.
- **Coding agents touch zero credentials.** You (Claude Code / Codex editing this repo) must never
  read the Keychain, `~/.ssh`, `~/.aws`, or any auth file. The `security` CLI and those paths are
  denied + guarded. Only the *running app* reads a credential, and only through one tiny isolated
  reader module that holds it in memory for a single read-only call and returns **numbers, never the
  token** (never logged, persisted, or sent to the browser).
- Use `.env.example` for documenting config keys (no real values).
- Localhost is not an auth boundary: the HTTP surface is read-only, and still sets an Origin check,
  CSRF protection, and a random per-session token (PLAN.md §9).
- If you spot a secret in the tree or history, stop and flag it immediately.

## Testing & coverage

- **Target 100% coverage on pure logic.** Our collectors/parsers are deliberately pure, so they
  should hit 100%. Any deliberate exclusion needs an inline reason: Python
  `# pragma: no cover  # reason: ...`, TS `/* c8 ignore next -- reason: ... */`. No silent gaps.
- **Be pragmatic on I/O glue** (subprocess, network, DB wiring): cover it where feasible, and
  isolate the untestable seam behind a thin adapter so the logic around it stays 100%.
- Every collector parser gets unit tests against real-shaped fixtures, including the degraded cases
  (missing fields, stale-after-reset, denied Keychain, endpoint 4xx/5xx). Don't mock away the thing
  under test; test the parser with captured (sanitized) payloads.
- **Coverage is gated in `/check`:** `pytest --cov` with a `fail-under` threshold (100% for `api/`
  logic modules), `vitest --coverage` with thresholds for `web/`. 100% line coverage is not
  correctness, so we keep it paired with the degraded-case fixtures above. Coverage config is wired
  in during scaffolding (issues #3, #4, #14).

## Git / PRs

- Branch off `main`; never commit directly to `main`. Conventional-ish commit messages.
- Run `/check` before opening a PR. CI (when added) must pass.
- Co-author trailer for AI commits: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## Skill routing

When a request matches a skill, invoke it via the Skill tool. Key routes:
- Product ideas / scope → `/office-hours`, then `/plan-ceo-review` / `/plan-eng-review`
- Bugs / errors → `/investigate` (root-cause first, no fixes without it)
- QA / does-it-work → `/qa` · Visual polish → `/design-review`
- Pre-merge diff check → `/review` · Independent second opinion → `/codex`
- Ship / PR → `/ship`

## How we work (agentic workflow)

Operating practices from Anthropic's published guidance. The deterministic ones are enforced by
hooks; the rest are how to drive the loop here.

- **Verify with evidence before claiming done.** Run `/check` and paste the result; for UI,
  screenshot vs. the target. Never assert success, show it. A `verify-gate` Stop hook also blocks
  turn-end on type errors once `web/`/`api/` exist (disable: `touch .claude/.verify-gate-off`).
- **Just-in-time, right-sized planning.** Multi-file or uncertain: plan mode, write a short spec
  (files, interfaces, out-of-scope, the verification step), then execute from a fresh session.
  One-line diffs: skip it. No heavy docs ahead of need.
- **Context is the scarce resource.** `/clear` between unrelated tasks; after two failed
  corrections, `/clear` and rewrite the prompt instead of patching on top. On compaction, preserve:
  read-only, tokens-never-leak, vendor-neutral, and the modified-files + test-commands list.
- **Headless runs are bounded.** Unattended `claude -p` runs MUST set `--max-turns` (a focused fix
  rarely needs >10) and a budget ceiling; log `total_cost_usd` from `--output-format json`. Budgets
  are per-invocation; fan-out multiplies them.
- **Token efficiency: native prompt caching.** Cache stable system prompts / large stable prefixes
  (cache reads are ~10% of input cost); use the Batch API for non-interactive jobs. We evaluated and
  **skipped Headroom** (in-band on our tokens, heavy deps, ~3% real bill savings on Claude traffic).
- **Fresh-context review before a PR.** `/code-review` (or `/codex`) on the diff vs. the plan;
  tell it to flag only correctness/requirement gaps (an open-ended "find problems" review
  manufactures scope creep against our lean-deps rule).
- **Self-improve.** End a substantial session by proposing CLAUDE.md additions for anything you had
  to correct, instead of re-correcting next time.

## Documentation & handoff (knowledge base)

We keep an HTML knowledge base in `docs/` so any newcomer or onboarding agent can grasp what has
been done and why. It is the durable memory of the project; chat history is not.

- **Format:** `docs/index.html` is the home; each unit of work is an entry `docs/NNNN-<slug>.html`
  built from `docs/_template.html`, structured **problem → solution → context** (the same shape the
  `/teach` skill uses). Self-contained HTML, no external dependencies.
- **Quality bar:** comprehensive but brief. Capture the *why* and the decisions/edge-cases, not a
  transcript. If a line would not help a new teammate or agent, cut it.
- **When to update (triggers):** before handing off to a new agent, before starting a new task, and
  at the context threshold below. Run **`/handoff`** to update the KB and emit a handoff prompt.
- **Context handoff rule:** when you reach roughly **60–65% of the context window**, stop taking on
  new work — update the knowledge base, run `/handoff` to produce a paste-ready handoff prompt, and
  recommend starting a fresh agent. (Honest limit: an agent cannot precisely self-measure remaining
  context, so treat this as a discipline + a cue to run `/handoff`, not a hard auto-trigger.)

## Recommended plugins / tooling (install at user level)

- **gstack** (already installed) — planning, review, QA, ship workflows.
- A **Codex second-opinion** pass on plans and risky diffs (we use `codex exec ... -s read-only`).
- Editor: ESLint + Prettier + Ruff extensions so local edits match the hooks.

## First task

The half-day spike (PLAN.md §10): prove the **Claude quota path** (Keychain → `/api/oauth/usage`)
first, it is the only real risk; Codex quota is already verified on disk. See `/spike`.
