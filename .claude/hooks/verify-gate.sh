#!/usr/bin/env bash
# Stop hook: verification gate (Anthropic best practice: give Claude a way to verify its work).
# Runs a FAST typecheck on web/ and api/ and blocks turn-end (exit 2) on type errors, up to a
# consecutive-block cap, then lets the turn end so it never wedges.
# Dormant until web/ or api/ exist. Fail-open on any internal error.
# Disable: touch .claude/.verify-gate-off   (or .verify-gate-off in the repo root)
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-$PWD}"
cat >/dev/null 2>&1 || true   # drain stdin (hook payload unused)
[ -f "$root/.claude/.verify-gate-off" ] && exit 0
[ -f "$root/.verify-gate-off" ] && exit 0
cd "$root" 2>/dev/null || exit 0

FAILS=""
checked=0
add_fail() { FAILS="${FAILS}"$'\n'"--- $1 FAILED ---"$'\n'"$2"; }

if [ -f web/package.json ] && command -v pnpm >/dev/null 2>&1; then
  checked=1
  if ! out="$( (cd web && pnpm -s typecheck) 2>&1 )"; then add_fail "web typecheck" "$out"; fi
fi
if [ -f api/pyproject.toml ] && command -v uv >/dev/null 2>&1; then
  checked=1
  if ! out="$( (cd api && uv run mypy) 2>&1 )"; then add_fail "api mypy" "$out"; fi
fi

[ "$checked" = "0" ] && exit 0   # nothing to verify yet (dormant)

cnt_file="${TMPDIR:-/tmp}/.mc-verify-gate.count"
if [ -z "$FAILS" ]; then rm -f "$cnt_file" 2>/dev/null; exit 0; fi   # clean

cnt=0; [ -f "$cnt_file" ] && cnt="$(cat "$cnt_file" 2>/dev/null || echo 0)"
cnt=$(( cnt + 1 )); printf '%s' "$cnt" > "$cnt_file" 2>/dev/null || true
if [ "$cnt" -ge 3 ]; then
  rm -f "$cnt_file" 2>/dev/null
  echo "verify-gate: type errors persist after $cnt attempts; ending the turn so you are not stuck. Fix types, or 'touch .claude/.verify-gate-off' to disable." >&2
  exit 0
fi
{ printf 'verify-gate: type errors must be fixed before finishing (attempt %s/3):' "$cnt"; printf '%b' "$FAILS"; } >&2
exit 2
