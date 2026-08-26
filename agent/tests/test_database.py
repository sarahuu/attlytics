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
