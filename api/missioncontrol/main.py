"""FastAPI app: read-only quota/usage endpoints + an SSE stream. Bind 127.0.0.1 only.

Run: `uv run uvicorn missioncontrol.main:app --host 127.0.0.1 --port 8787`
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .service import snapshot

POLL_SECONDS = 30

app = FastAPI(title="Mission Control API", version="0.1.0")

# Read-only, local-first: only the local dev web origin may call us; GET only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/quota")
def quota() -> dict[str, object]:
    return snapshot()


@app.get("/api/events")
async def events(request: Request) -> StreamingResponse:
    async def gen() -> AsyncIterator[str]:
        while True:
            if await request.is_disconnected():
                break
            yield f"data: {json.dumps(snapshot())}\n\n"
            await asyncio.sleep(POLL_SECONDS)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
