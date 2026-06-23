"""HTTP-layer smoke tests (exercise main.py + service.py against real local data).

These hit the I/O seam end to end; the store-backed tests redirect MC_DB_PATH to a temp DB so
nothing is written under the real home directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from missioncontrol.main import app

# base_url is localhost so the Host header passes the DNS-rebinding guard (issue #13).
client = TestClient(app, base_url="http://127.0.0.1:8787")


def test_health() -> None:
    assert client.get("/api/health").json() == {"ok": True}


def test_session_returns_a_token() -> None:
    body = client.get("/api/session").json()
    assert isinstance(body["token"], str) and len(body["token"]) > 20


def test_guard_rejects_foreign_origin() -> None:
    r = client.get("/api/quota", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_guard_rejects_rebinding_host() -> None:
    r = client.get("/api/quota", headers={"Host": "attacker.com"})
    assert r.status_code == 403


def test_guard_allows_dev_web_origin() -> None:
    r = client.get("/api/quota", headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200


def test_quota_shape() -> None:
    body = client.get("/api/quota").json()
    assert set(body) == {"generated_at", "codex", "claude"}
    assert "available" in body["codex"]
    assert "available" in body["claude"]


def test_timeline_seeded_on_startup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MC_DB_PATH", str(tmp_path / "events.db"))
    with TestClient(app, base_url="http://127.0.0.1:8787") as ctx:  # lifespan: init + seed
        body = ctx.get("/api/timeline").json()
    assert isinstance(body["events"], list)
    # With no agent files present, the seed still records collector-status rows.
    assert len(body["events"]) >= 1
    assert all({"surface", "type", "ts", "severity"} <= set(e) for e in body["events"])


def test_timeline_degraded_when_uninitialized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MC_DB_PATH", str(tmp_path / "missing.db"))
    body = client.get("/api/timeline").json()  # module-level client: no lifespan, no DB file
    assert body["events"] == []
    assert body["degraded"]
