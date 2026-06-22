---
description: Start the Mission Control dev stack — FastAPI backend + Next.js frontend, both on localhost.
---

Start both dev servers as background processes, confirm they are up, and print the local URLs.

- Backend: `cd api && uv run fastapi dev` (must bind 127.0.0.1 only)
- Frontend: `cd web && pnpm dev`

Everything binds to `127.0.0.1` only — never expose publicly. Tail both for startup errors and
report them. If a directory does not exist yet, say so instead of failing silently.
