import json

from agent.storage.database import ActivityDatabase


def _event(**overrides):
    event = {
        "id": "event-1",
        "state_id": "state-1",
        "source": "os",
        "application": "code.exe",
        "event_type": "STATE_START",
        "timestamp": "2026-08-26T10:00:00+00:00",
        "duration_seconds": 0,
        "metadata": {"process_id": 1, "window_title": "main.py"},
        "sync_status": "PENDING",
    }
    event.update(overrides)
    return event


def test_initialize_and_insert(tmp_path):
    db = ActivityDatabase(tmp_path / "test.db")
    db.initialize()
    db.insert_event(_event())

    assert db.count_events() == 1
    db.close()


def test_default_sync_status_is_pending(tmp_path):
    db = ActivityDatabase(tmp_path / "test.db")
    db.initialize()
    event = _event()
    del event["sync_status"]
    db.insert_event(event)

    stored = db.get_events()[0]
    assert stored["sync_status"] == "PENDING"
    db.close()


def test_metadata_is_serialized_as_json(tmp_path):
    db = ActivityDatabase(tmp_path / "test.db")
    db.initialize()
    db.insert_event(_event())

    stored = db.get_events()[0]
    assert json.loads(stored["metadata"]) == {
        "process_id": 1,
        "window_title": "main.py",
    }
    db.close()


def test_get_events_filters_by_state_id_and_type(tmp_path):
    db = ActivityDatabase(tmp_path / "test.db")
    db.initialize()
    db.insert_event(_event(id="1", state_id="a", event_type="STATE_START"))
    db.insert_event(_event(id="2", state_id="a", event_type="HEARTBEAT"))
    db.insert_event(_event(id="3", state_id="b", event_type="STATE_START"))

    assert len(db.get_events(state_id="a")) == 2
    assert len(db.get_events(event_type="HEARTBEAT")) == 1
    assert len(db.get_events(state_id="b", event_type="STATE_START")) == 1
    db.close()


def test_events_persist_after_close_and_reopen(tmp_path):
    db = ActivityDatabase(tmp_path / "test.db")
    db.initialize()
    db.insert_event(_event())
    db.close()

    reopened = ActivityDatabase(tmp_path / "test.db")
    reopened.initialize()
    assert reopened.count_events() == 1
    assert reopened.get_events()[0]["application"] == "code.exe"
    reopened.close()


def test_pending_events_are_oldest_first(tmp_path):
    db = ActivityDatabase(tmp_path / "test.db")
    db.initialize()
    db.insert_event(_event(id="newer", timestamp="2026-08-26T10:00:09+00:00"))
    db.insert_event(_event(id="older", timestamp="2026-08-26T10:00:01+00:00"))

    assert [event["id"] for event in db.get_pending_events()] == ["older", "newer"]
    db.close()


def test_mark_synced_and_record_failure(tmp_path):
    db = ActivityDatabase(tmp_path / "test.db")
    db.initialize()
    db.insert_event(_event(id="e1"))
    db.insert_event(_event(id="e2"))

    db.record_sync_failure(["e1"], error="HTTP 503", next_retry_at="later")
    failed = [event for event in db.get_events() if event["id"] == "e1"][0]
    assert failed["sync_status"] == "PENDING"
    assert failed["attempt_count"] == 1
    assert failed["last_sync_error"] == "HTTP 503"
    assert failed["next_retry_at"] == "later"

    db.mark_synced(["e2"])
    synced = [event for event in db.get_events() if event["id"] == "e2"][0]
    assert synced["sync_status"] == "SYNCED"
    assert db.count_pending_events() == 1
    db.close()


def test_settings_round_trip(tmp_path):
    db = ActivityDatabase(tmp_path / "test.db")
    db.initialize()

    assert db.get_setting("sync_enabled", "1") == "1"
    db.set_setting("sync_enabled", "0")
    assert db.get_setting("sync_enabled") == "0"
    db.set_setting("sync_enabled", "1")
    assert db.get_setting("sync_enabled") == "1"
    db.close()


def test_existing_database_gains_sync_columns(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE activity_events ("
        "id TEXT PRIMARY KEY, state_id TEXT NOT NULL, source TEXT NOT NULL, "
        "application TEXT NOT NULL, event_type TEXT NOT NULL, "
        "timestamp TEXT NOT NULL, duration_seconds REAL, metadata TEXT, "
        "sync_status TEXT NOT NULL DEFAULT 'PENDING')"
    )
    conn.execute(
        "INSERT INTO activity_events "
        "(id, state_id, source, application, event_type, timestamp) "
        "VALUES ('e1', 's1', 'os', 'code.exe', 'STATE_START', "
        "'2026-08-26T10:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    db = ActivityDatabase(path)
    db.initialize()  # should ALTER TABLE in the missing columns

    stored = db.get_events()[0]
    assert stored["attempt_count"] == 0
    assert stored["next_retry_at"] is None
    assert db.count_pending_events() == 1
    db.close()
