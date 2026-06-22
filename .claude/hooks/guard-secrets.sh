#!/usr/bin/env bash
# PreToolUse hook: block writing secret-bearing files or pasting token-shaped strings.
# Exit 2 = block the tool call (stderr is shown to the agent).
set -uo pipefail

input="$(cat)"

fp="$(printf '%s' "$input" | python3 -c 'import sys,json
try: print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))
except Exception: print("")' 2>/dev/null)"

content="$(printf '%s' "$input" | python3 -c 'import sys,json
try:
    ti=json.load(sys.stdin).get("tool_input",{})
    print(ti.get("content","") or ti.get("new_string","") or "")
except Exception:
    print("")' 2>/dev/null)"

# Allow documentation templates.
case "$fp" in
  *.env.example|*.env.sample|*.env.template) : ;;
  *.env|*/.env|*.env.*|*.pem|*.key|*/secrets/*|*/.ssh/*|*id_rsa*|*id_ed25519*|*/.claude/settings.local.json)
    echo "BLOCKED by guard-secrets: refusing to read/write secret-bearing file '$fp'. Tokens live in the OS Keychain, never the repo. Use a .env.example (no real values) to document config." >&2
    exit 2
    ;;
esac

# Block obvious token/secret material in the content being written.
if printf '%s' "$content" | grep -Eq 'sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{20,}|gh[posru]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----'; then
  echo "BLOCKED by guard-secrets: the content looks like it contains a secret/token. Never commit secrets; read them from the OS Keychain or env at runtime." >&2
  exit 2
fi

exit 0
