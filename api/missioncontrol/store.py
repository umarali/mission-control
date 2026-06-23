"""SQLite event store (the I/O seam for the event spine; PLAN.md §5).

Isolated and thin on purpose: the *logic* (deriving + scrubbing rows) lives in events.py and is
100%-covered; this module is the DB wiring, exercised by tests against a temp DB but kept out of
the unit-coverage gate (like paths.py). Uses the stdlib ``sqlite3`` — no new dependency.

Hardening (issue #13): the DB file is created 0600 (owner-only). Payloads are already scrubbed
upstream, so even the on-disk rows never contain a secret.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .models import Event

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  surface        TEXT    NOT NULL,
  source         TEXT    NOT NULL,
  session_id     TEXT,
  work_thread_id TEXT,
  type           TEXT    NOT NULL,
  ts             INTEGER NOT NULL,
  severity       TEXT    NOT NULL,
  payload        TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_surface ON events(surface);
"""


def default_db_path() -> Path:
    """Local-first default, overridable with ``MC_DB_PATH``."""
    env = os.environ.get("MC_DB_PATH")
    if env:
        return Path(env)
    return Path.home() / ".mission-control" / "events.db"


class EventStore:
    """Append-only store over a single local SQLite DB. Short-lived connections per op."""

    def __init__(self, path: Path | str | None = None) -> None:
        # Resolve lazily when unset so MC_DB_PATH is honored at call time (and tests can redirect).
        self._path = Path(path) if path is not None else None

    @property
    def path(self) -> Path:
        return self._path if self._path is not None else default_db_path()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init(self) -> None:
        """Create the parent dir + schema, set owner-only perms, run migrations. Idempotent."""
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        # Touch with 0600 before SQLite creates it, so the DB is never group/world-readable.
        if not path.exists():
            path.touch(mode=0o600)
        else:
            os.chmod(path, 0o600)
        with self._connect() as conn:
            version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            if version < SCHEMA_VERSION:
                conn.executescript(_SCHEMA)
                conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            conn.commit()

    def append(self, events: Iterable[Event]) -> int:
        """Insert events; returns the number written."""
        rows = [
            (
                e.surface,
                e.source,
                e.session_id,
                e.work_thread_id,
                e.type,
                e.ts,
                e.severity,
                json.dumps(e.payload, separators=(",", ":")),
            )
            for e in events
        ]
        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO events "
                "(surface, source, session_id, work_thread_id, type, ts, severity, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()
        return len(rows)

    def recent(self, limit: int = 100, surface: str | None = None) -> list[Event]:
        """Most recent events first, optionally filtered by surface."""
        sql = "SELECT * FROM events"
        params: list[object] = []
        if surface is not None:
            sql += " WHERE surface = ?"
            params.append(surface)
        sql += " ORDER BY ts DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            cur = conn.execute(sql, params)
            return [_row_to_event(r) for r in cur.fetchall()]

    def prune(self, max_rows: int) -> int:
        """Retention cap: keep only the newest ``max_rows`` rows. Returns rows deleted."""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM events WHERE id NOT IN "
                "(SELECT id FROM events ORDER BY id DESC LIMIT ?)",
                (max_rows,),
            )
            conn.commit()
            return cur.rowcount


def _row_to_event(r: sqlite3.Row) -> Event:
    return Event(
        id=r["id"],
        surface=r["surface"],
        source=r["source"],
        session_id=r["session_id"],
        work_thread_id=r["work_thread_id"],
        type=r["type"],
        ts=r["ts"],
        severity=r["severity"],
        payload=json.loads(r["payload"]),
    )
