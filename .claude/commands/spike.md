---
description: Execute the v1 first spike — prove the Claude quota path, then Codex (PLAN.md §10). Throwaway.
---

Implement the throwaway spike from PLAN.md §10. Goal: print real remaining-% + reset for BOTH
agents from real local data, honoring every rule in CLAUDE.md. This is throwaway — do not over-build.

1. **Claude (the real risk).** Read the OAuth token from the macOS Keychain via
   `/usr/bin/security find-generic-password -w` (discover the exact service/account name first),
   then a read-only `GET https://api.anthropic.com/api/oauth/usage` with header
   `anthropic-beta: oauth-2025-04-20`. Print remaining % + reset for `five_hour` and `seven_day`.
   - NO `max_tokens:1` probe (never spend quota to measure quota).
   - Spawn `security` by absolute path + fixed argv, no shell; scrub its output; never log the token.
   - Verify clean degraded states on denied/locked Keychain and on endpoint 4xx/5xx.

2. **Codex.** Parse the newest `~/.codex/sessions/<today>/rollout-*.jsonl`, last `token_count`
   event, read `payload.rate_limits` (`primary` = 5h, `secondary` = weekly): `remaining = 100 -
   used_percent`, plus reset. Label windows by `window_minutes`. Flag stale-after-reset.

**Success:** four real numbers print; no token persisted or logged; degraded states work; 429/backoff
behaves on the Claude endpoint. Report results and what (if anything) was surprising.
