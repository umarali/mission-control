"""FastAPI app: read-only quota/usage endpoints + an SSE stream. Bind 127.0.0.1 only.

Run: `uv run uvicorn missioncontrol.main:app --host 127.0.0.1 --port 8787`
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .redact import redact_text
from .security import host_allowed, new_session_token, origin_allowed
from .service import get_store, record_snapshot, snapshot, transcript

POLL_SECONDS = 30


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Init the event store and seed one snapshot so the timeline has data immediately.
    try:
        get_store().init()
        record_snapshot()
    except Exception:  # noqa: BLE001  # reason: store init must never block serving the gauges
        pass
    yield


app = FastAPI(title="Mission Control API", version="0.2.0", lifespan=lifespan)

# Per-session token (issue #13): regenerated each process start. v1 exposes it as a baseline;
# the v1.5 action surface will require it. Set at import so it exists with or without lifespan.
app.state.session_token = new_session_token()

# Read-only, local-first: only the local dev web origin may call us; GET only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def localhost_guard(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Reject DNS-rebinding (bad Host) and cross-site browser reads (bad Origin) before routing."""
    if not host_allowed(request.headers.get("host")):
        return JSONResponse({"detail": "host not allowed"}, status_code=403)
    if not origin_allowed(request.headers.get("origin")):
        return JSONResponse({"detail": "origin not allowed"}, status_code=403)
    return await call_next(request)


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/session")
def session(request: Request) -> dict[str, str]:
    """The per-session token (Origin/Host-guarded). Baseline for the v1.5 action surface."""
    token: str = request.app.state.session_token
    return {"token": token}


@app.get("/api/quota")
def quota() -> dict[str, object]:
    return snapshot()


@app.get("/api/transcript")
def transcript_endpoint(agent: str = "claude", limit: int = 200) -> dict[str, object]:
    """Read-only rendered transcript (watch-feed) for an agent's newest local session."""
    limit = max(1, min(limit, 1000))
    return transcript(agent, limit=limit)


@app.get("/api/timeline")
def timeline(limit: int = 100, surface: str | None = None) -> dict[str, object]:
    """Recent normalized events from the local store (newest first). Degrades to empty."""
    limit = max(1, min(limit, 500))
    store = get_store()
    if not store.path.exists():
        return {"events": [], "degraded": "event store not initialized"}
    try:
        events = [asdict(e) for e in store.recent(limit=limit, surface=surface)]
        return {"events": events}
    except Exception as exc:  # noqa: BLE001  # reason: degrade-never-lie on any store read error
        return {"events": [], "degraded": redact_text(str(exc))}


@app.get("/api/events")
async def events(request: Request) -> StreamingResponse:
    async def gen() -> AsyncIterator[str]:
        while True:
            if await request.is_disconnected():
                break
            yield f"data: {json.dumps(record_snapshot())}\n\n"
            await asyncio.sleep(POLL_SECONDS)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
