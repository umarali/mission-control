#!/usr/bin/env bash
# PostToolUse hook: auto-format an edited file. Best-effort, never fails the tool.
set -uo pipefail

input="$(cat)"
fp="$(printf '%s' "$input" | python3 -c 'import sys,json
try: print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))
except Exception: print("")' 2>/dev/null)"

[ -n "${fp:-}" ] && [ -f "$fp" ] || exit 0
case "$fp" in
  */node_modules/*|*/.next/*|*/dist/*|*/.venv/*) exit 0 ;;
esac

case "$fp" in
  *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.css)
    if command -v prettier >/dev/null 2>&1; then
      prettier --write "$fp" >/dev/null 2>&1 || true
    elif command -v pnpm >/dev/null 2>&1; then
      pnpm exec prettier --write "$fp" >/dev/null 2>&1 || true
    fi
    ;;
  *.py)
    if command -v ruff >/dev/null 2>&1; then
      ruff format "$fp" >/dev/null 2>&1 || true
      ruff check --fix "$fp" >/dev/null 2>&1 || true
    elif command -v uv >/dev/null 2>&1; then
      uv run ruff format "$fp" >/dev/null 2>&1 || true
      uv run ruff check --fix "$fp" >/dev/null 2>&1 || true
    fi
    ;;
esac
exit 0
