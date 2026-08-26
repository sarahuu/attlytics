import json
import sqlite3
from pathlib import Path

from agent.config import DB_PATH


class ActivityDatabase:
    """
    Local SQLite persistence for activity events.

    The client only records observations; session derivation is a server-side
    concern. This store is the durable event log that the sync worker will
    later read from.
    """

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = None

    def _connect(self):
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.path))
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
        return self._connection

    def initialize(self):
        """Create the activity-events table and indexes if they do not exist."""
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_events (
                id               TEXT PRIMARY KEY,
                state_id         TEXT NOT NULL,
                source           TEXT NOT NULL,
                application      TEXT NOT NULL,
                event_type       TEXT NOT NULL,
                timestamp        TEXT NOT NULL,
                duration_seconds REAL,
                metadata         TEXT,
                sync_status      TEXT NOT NULL DEFAULT 'PENDING'
            )
            """
        )
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
        conn.commit()

    def insert_event(self, event):
        """Persist a single activity event. The `metadata` value, if a dict,
        is serialized to JSON."""
        conn = self._connect()
        metadata = event.get("metadata")
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
        conn = self._connect()
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

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def count_events(self):
        """Total number of stored events."""
        conn = self._connect()
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM activity_events"
        ).fetchone()
        return row["total"]

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None
