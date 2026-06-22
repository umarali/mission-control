---
description: Run lint, type-check, and tests across the Next.js frontend (web/) and the Python backend (api/).
---

Run the full quality gate and report a concise PASS/FAIL summary per category. Do not fix anything unless asked.

Frontend (only if `web/` exists):
- `cd web && pnpm lint`
- `cd web && pnpm typecheck`
- `cd web && pnpm test`

Backend (only if `api/` exists):
- `cd api && uv run ruff check .`
- `cd api && uv run mypy .`
- `cd api && uv run pytest`

Stop at the first category with failures and show the relevant output. End with a one-line verdict.
