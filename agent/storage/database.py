import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from agent.config import DB_PATH

_SYNC_COLUMNS = {
    "attempt_count": "INTEGER NOT NULL DEFAULT 0",
    "last_sync_attempt": "TEXT",
    "next_retry_at": "TEXT",
    "last_sync_error": "TEXT",
}


class ActivityDatabase:
    """
    Local SQLite persistence for activity events.

    The client only records observations; session derivation is a server-side
    concern. This store is the durable event log the sync worker reads from.

    The tracker thread and the sync worker thread share one connection, so
    every statement is serialized behind ``_lock``.
    """

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = None
        self._lock = threading.Lock()

    def _connect(self):
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.path), check_same_thread=False
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
        return self._connection

    def initialize(self):
        """Create or upgrade the schema. Safe to call on every start."""
        with self._lock:
            conn = self._connect()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_events (
                    id                TEXT PRIMARY KEY,
                    state_id          TEXT NOT NULL,
                    source            TEXT NOT NULL,
                    application       TEXT NOT NULL,
                    event_type        TEXT NOT NULL,
                    timestamp         TEXT NOT NULL,
                    duration_seconds  REAL,
                    metadata          TEXT,
                    sync_status       TEXT NOT NULL DEFAULT 'PENDING',
                    attempt_count     INTEGER NOT NULL DEFAULT 0,
                    last_sync_attempt TEXT,
                    next_retry_at     TEXT,
                    last_sync_error   TEXT
                )
                """
            )
            self._add_missing_sync_columns(conn)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_state_id "
                "ON activity_events (state_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_timestamp "
                "ON activity_events (timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_sync_status "
                "ON activity_events (sync_status)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.commit()

    @staticmethod
    def _add_missing_sync_columns(conn):
        """Add sync-metadata columns to databases created without them."""
        existing = {
            row["name"] for row in conn.execute("PRAGMA table_info(activity_events)")
        }
        for name, definition in _SYNC_COLUMNS.items():
            if name not in existing:
                conn.execute(
                    f"ALTER TABLE activity_events ADD COLUMN {name} {definition}"
                )

    def insert_event(self, event):
        """Persist a single activity event. The `metadata` value, if a dict,
        is serialized to JSON."""
        metadata = event.get("metadata")
        with self._lock:
            conn = self._connect()
            conn.execute(
                """
                INSERT INTO activity_events
                    (id, state_id, source, application, event_type, timestamp,
                     duration_seconds, metadata, sync_status)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    event["state_id"],
                    event["source"],
                    event["application"],
                    event["event_type"],
                    event["timestamp"],
                    event.get("duration_seconds"),
                    json.dumps(metadata) if metadata is not None else None,
                    event.get("sync_status", "PENDING"),
                ),
            )
            conn.commit()

    def get_events(self, state_id=None, source=None, event_type=None, limit=None):
        """Return events ordered by timestamp, optionally filtered."""
        query = "SELECT * FROM activity_events WHERE 1 = 1"
        params = []

        if state_id is not None:
            query += " AND state_id = ?"
            params.append(state_id)
        if source is not None:
            query += " AND source = ?"
            params.append(source)
        if event_type is not None:
            query += " AND event_type = ?"
            params.append(event_type)

        query += " ORDER BY timestamp"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self._lock:
            rows = self._connect().execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_pending_events(self, limit=100):
        """Return pending events, oldest first, for the sync worker.

        Timestamps are stored as UTC ISO-8601, so lexical order is
        chronological order.
        """
        with self._lock:
            rows = self._connect().execute(
                """
                SELECT * FROM activity_events
                WHERE sync_status = 'PENDING'
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def count_events(self):
        """Total number of stored events."""
        with self._lock:
            row = self._connect().execute(
                "SELECT COUNT(*) AS total FROM activity_events"
            ).fetchone()
            return row["total"]

    def count_pending_events(self):
        """Number of events still waiting to be uploaded."""
        with self._lock:
            row = self._connect().execute(
                "SELECT COUNT(*) AS total FROM activity_events "
                "WHERE sync_status = 'PENDING'"
            ).fetchone()
            return row["total"]

    def mark_synced(self, event_ids):
        """Mark events as delivered. Only called after a 2xx response."""
        if not event_ids:
            return
        placeholders = ",".join("?" for _ in event_ids)
        with self._lock:
            conn = self._connect()
            conn.execute(
                "UPDATE activity_events SET sync_status = 'SYNCED', "
                "last_sync_attempt = ?, last_sync_error = NULL, "
                "next_retry_at = NULL "
                f"WHERE id IN ({placeholders})",
                [datetime.now(UTC).isoformat(), *event_ids],
            )
            conn.commit()

    def record_sync_failure(self, event_ids, error, next_retry_at=None):
        """Record a failed attempt. Events stay PENDING and are retried."""
        if not event_ids:
            return
        placeholders = ",".join("?" for _ in event_ids)
        with self._lock:
            conn = self._connect()
            conn.execute(
                "UPDATE activity_events SET "
                "attempt_count = attempt_count + 1, "
                "last_sync_attempt = ?, next_retry_at = ?, last_sync_error = ? "
                f"WHERE id IN ({placeholders})",
                [
                    datetime.now(UTC).isoformat(),
                    next_retry_at,
                    error,
                    *event_ids,
                ],
            )
            conn.commit()

    def get_setting(self, key, default=None):
        """Read a persisted agent setting (e.g. whether sync is enabled)."""
        with self._lock:
            row = self._connect().execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row is not None else default

    def set_setting(self, key, value):
        with self._lock:
            conn = self._connect()
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
            conn.commit()

    def close(self):
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
