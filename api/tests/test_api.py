"""HTTP-layer smoke tests (exercise main.py + service.py against real local data)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from missioncontrol.main import app

client = TestClient(app)


def test_health() -> None:
    assert client.get("/api/health").json() == {"ok": True}


def test_quota_shape() -> None:
    body = client.get("/api/quota").json()
    assert set(body) == {"generated_at", "codex", "claude"}
    assert "available" in body["codex"]
    assert "available" in body["claude"]
