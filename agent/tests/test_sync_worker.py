import threading
import urllib.error

from agent.storage.database import ActivityDatabase
from agent.sync_worker import SYNC_ENABLED_SETTING, SyncWorker, retry_delay_seconds


class RecordingPoster:
    """Stands in for the HTTP call: records batches, or raises."""

    def __init__(self, error=None):
        self.batches = []
        self.error = error

    def __call__(self, payload, api_key):
        self.batches.append((payload, api_key))
        if self.error is not None:
            raise self.error
        return {"received": len(payload), "skipped": 0}


def _event(**overrides):
    event = {
        "id": "event-1",
        "state_id": "state-1",
        "source": "os",
        "application": "code.exe",
        "event_type": "STATE_START",
        "timestamp": "2026-08-26T10:00:00+00:00",
        "duration_seconds": 0.0,
        "metadata": {"process_id": 7, "window_title": "main.py"},
    }
    event.update(overrides)
    return event


def _make_worker(tmp_path, poster, api_key="key-123", **kwargs):
    db = ActivityDatabase(tmp_path / "test.db")
    db.initialize()
    worker = SyncWorker(
        storage=db,
        stop_event=threading.Event(),
        api_base_url="http://api.test",
        api_key_loader=lambda: api_key,
        poster=poster,
        **kwargs,
    )
    return db, worker


def test_retry_delay_schedule():
    assert retry_delay_seconds(1) == 60.0
    assert retry_delay_seconds(2) == 120.0
    assert retry_delay_seconds(3) == 240.0
    assert retry_delay_seconds(4) == 300.0
    assert retry_delay_seconds(50) == 300.0


def test_successful_batch_is_marked_synced(tmp_path):
    db, worker = _make_worker(tmp_path, RecordingPoster())
    db.insert_event(_event(id="e1", timestamp="2026-08-26T10:00:01+00:00"))
    db.insert_event(_event(id="e2", timestamp="2026-08-26T10:00:02+00:00"))

    assert worker._run_once() == 0.0

    assert db.count_pending_events() == 0
    assert {event["sync_status"] for event in db.get_events()} == {"SYNCED"}
    db.close()


def test_batch_is_sent_oldest_first(tmp_path):
    poster = RecordingPoster()
    db, worker = _make_worker(tmp_path, poster)
    db.insert_event(_event(id="newer", timestamp="2026-08-26T10:00:09+00:00"))
    db.insert_event(_event(id="older", timestamp="2026-08-26T10:00:01+00:00"))

    worker._run_once()

    sent = poster.batches[0][0]
    assert [item["local_id"] for item in sent] == ["older", "newer"]
    db.close()


def test_batch_size_is_respected(tmp_path):
    poster = RecordingPoster()
    db, worker = _make_worker(tmp_path, poster, batch_size=2)
    for index in range(5):
        db.insert_event(
            _event(id=f"e{index}", timestamp=f"2026-08-26T10:00:0{index}+00:00")
        )

    worker._run_once()

    assert len(poster.batches[0][0]) == 2
    assert db.count_pending_events() == 3
    db.close()


def test_temporary_failure_keeps_events_pending(tmp_path):
    poster = RecordingPoster(error=urllib.error.URLError("no route to host"))
    db, worker = _make_worker(tmp_path, poster)
    db.insert_event(_event(id="e1"))

    assert worker._run_once() == 60.0

    stored = db.get_events()[0]
    assert stored["sync_status"] == "PENDING"  # never FAILED
    assert stored["attempt_count"] == 1
    assert stored["last_sync_error"]
    assert stored["next_retry_at"]
    db.close()


def test_backoff_grows_then_resets_after_success(tmp_path):
    poster = RecordingPoster(
        error=urllib.error.HTTPError("u", 503, "busy", {}, None)
    )
    db, worker = _make_worker(tmp_path, poster)
    db.insert_event(_event(id="e1"))

    assert worker._run_once() == 60.0
    assert worker._run_once() == 120.0
    assert worker._run_once() == 240.0
    assert worker._run_once() == 300.0

    poster.error = None
    assert worker._run_once() == 0.0

    db.insert_event(_event(id="e2"))
    poster.error = urllib.error.URLError("down")
    assert worker._run_once() == 60.0  # reset by the successful sync
    db.close()


def test_disabled_worker_sends_nothing(tmp_path):
    poster = RecordingPoster()
    db, worker = _make_worker(tmp_path, poster)
    db.insert_event(_event(id="e1"))
    worker.set_enabled(False)

    assert worker._run_once() is None  # waits for a wake-up
    assert poster.batches == []
    assert db.count_pending_events() == 1
    db.close()


def test_enabling_persists_and_wakes_the_worker(tmp_path):
    db, worker = _make_worker(tmp_path, RecordingPoster())
    worker.set_enabled(False)
    assert db.get_setting(SYNC_ENABLED_SETTING) == "0"

    worker._wake.clear()
    worker.set_enabled(True)

    assert worker.is_enabled() is True
    assert db.get_setting(SYNC_ENABLED_SETTING) == "1"
    assert worker._wake.is_set()  # woken immediately, no waiting for a tick

    # A fresh worker picks the persisted choice back up.
    restarted = SyncWorker(
        storage=db,
        stop_event=threading.Event(),
        api_base_url="http://api.test",
        api_key_loader=lambda: "key",
        poster=RecordingPoster(),
    )
    assert restarted.is_enabled() is True
    db.close()


def test_no_api_key_is_a_temporary_failure(tmp_path):
    poster = RecordingPoster()
    db, worker = _make_worker(tmp_path, poster, api_key=None)
    db.insert_event(_event(id="e1"))

    assert worker._run_once() == 60.0
    assert poster.batches == []
    assert db.get_events()[0]["sync_status"] == "PENDING"
    db.close()


def test_payload_maps_local_event_to_api_schema(tmp_path):
    poster = RecordingPoster()
    db, worker = _make_worker(tmp_path, poster)
    db.insert_event(_event(id="e1"))

    worker._run_once()

    assert poster.batches[0][0][0] == {
        "local_id": "e1",
        "state_id": "state-1",
        "source": "os",
        "application": "code.exe",
        "event_type": "STATE_START",
        "timestamp": "2026-08-26T10:00:00+00:00",
        "duration_seconds": 0.0,
        "process_id": 7,
        "window_title": "main.py",
    }
    db.close()
