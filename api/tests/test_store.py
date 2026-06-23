"""Integration tests for the SQLite event store, against a temp DB.

store.py is the I/O seam (omitted from the unit-coverage gate), but it is still verified here:
schema/migrations, append+read round-trip, surface filter, owner-only perms, and retention.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from missioncontrol.models import Event
from missioncontrol.store import SCHEMA_VERSION, EventStore, default_db_path


def _ev(ts: int, surface: str = "codex", **kw: object) -> Event:
    return Event(surface=surface, source="t", type="quota.snapshot", ts=ts, severity="info", **kw)  # type: ignore[arg-type]


def test_init_is_idempotent_and_sets_version(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.db")
    store.init()
    store.init()  # second call must not error or downgrade
    import sqlite3

    with sqlite3.connect(store.path) as conn:
        assert int(conn.execute("PRAGMA user_version").fetchone()[0]) == SCHEMA_VERSION


def test_db_file_is_owner_only(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.db")
    store.init()
    mode = stat.S_IMODE(os.stat(store.path).st_mode)
    assert mode & 0o077 == 0  # no group/world bits


def test_append_and_recent_round_trip(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.db")
    store.init()
    assert store.append([]) == 0  # nothing to write
    n = store.append([_ev(1, payload={"a": 1}), _ev(2, surface="claude", session_id="s1")])
    assert n == 2
    rows = store.recent()
    assert [r.ts for r in rows] == [2, 1]  # newest first
    assert rows[0].surface == "claude" and rows[0].session_id == "s1"
    assert rows[1].payload == {"a": 1} and rows[1].id is not None


def test_recent_filters_by_surface_and_limit(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.db")
    store.init()
    store.append([_ev(1), _ev(2, surface="claude"), _ev(3)])
    assert [r.surface for r in store.recent(surface="codex")] == ["codex", "codex"]
    assert len(store.recent(limit=1)) == 1


def test_prune_keeps_only_newest(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "events.db")
    store.init()
    store.append([_ev(i) for i in range(5)])
    deleted = store.prune(max_rows=2)
    assert deleted == 3
    assert len(store.recent()) == 2


def test_default_db_path_honors_env(monkeypatch: object, tmp_path: Path) -> None:
    # monkeypatch is a pytest fixture; typed loosely to avoid importing the plugin's types.
    mp = monkeypatch  # type: ignore[assignment]
    mp.setenv("MC_DB_PATH", str(tmp_path / "custom.db"))  # type: ignore[attr-defined]
    assert default_db_path() == tmp_path / "custom.db"
    mp.delenv("MC_DB_PATH")  # type: ignore[attr-defined]
    assert default_db_path().name == "events.db"
