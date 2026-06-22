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
- Use `.env.example` for documenting config keys (no real values).
- Localhost is not an auth boundary: the HTTP surface is read-only, and still sets an Origin check,
  CSRF protection, and a random per-session token (PLAN.md §9).
- If you spot a secret in the tree or history, stop and flag it immediately.

## Testing

- Every collector parser gets unit tests against real-shaped fixtures, including the degraded
  cases (missing fields, stale-after-reset, denied Keychain, endpoint 4xx/5xx).
- Don't mock away the thing under test. Test the parser with captured (sanitized) payloads.

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

## Recommended plugins / tooling (install at user level)

- **gstack** (already installed) — planning, review, QA, ship workflows.
- A **Codex second-opinion** pass on plans and risky diffs (we use `codex exec ... -s read-only`).
- Editor: ESLint + Prettier + Ruff extensions so local edits match the hooks.

## First task

The half-day spike (PLAN.md §10): prove the **Claude quota path** (Keychain → `/api/oauth/usage`)
first, it is the only real risk; Codex quota is already verified on disk. See `/spike`.
