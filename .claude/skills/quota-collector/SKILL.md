---
name: quota-collector
description: Use when adding or modifying a quota/usage collector or any vendor data source in api/. Enforces this codebase's read-only, token-safety, tolerant-parsing, and degrade-never-lie rules.
---

# Adding a quota / data collector

Apply these rules (from CLAUDE.md + PLAN.md) to any collector that reads agent or vendor data.

## Hard rules
- **Read-only.** No write calls to vendor APIs. Never spend quota to measure quota (no
  `max_tokens:1` probes).
- **Vendor's number, never guess.** Use the server-authoritative percentage (`utilization` /
  `used_percent`). Never hardcode plan caps. Label rate-limit windows by `window_minutes`, never by
  field position (e.g. `secondary` can be null on free tiers).
- **Token safety.** Read tokens at call time, hold in memory only, never persist/log/send to the
  browser, redact from errors. For Keychain tokens, spawn `/usr/bin/security` by absolute path with
  a fixed argv list (no `shell=True`); scrub its output.
- **Tolerant parsing.** Handle schema drift, partial writes, null fields, file rollover. On any
  failure return a `degraded` / `stale` state, never crash and never return a wrong number.

## Shape
Each collector is a pure async function returning, per window:
`{ agent, window, window_minutes, remaining_pct, resets_at, plan_type, blocked, stale, degraded }`.
Keep the parsing pure (separate from I/O) so it is directly unit-testable.

## Tests (required)
pytest cases for: happy path, missing fields, stale-after-reset, denied/locked Keychain (Claude),
endpoint 4xx/5xx (Claude). Use sanitized real-shaped fixtures. Do not mock the parser itself.

## Reference
PLAN.md §5 (mechanisms), §9 (architecture + subprocess hardening), §10 (spike).
