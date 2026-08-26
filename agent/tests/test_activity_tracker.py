import pytest

from agent.storage.database import ActivityDatabase
from agent.tests.fakes import FakeClock, FakeObserver
from agent.tracking.activity_tracker import (
    HEARTBEAT,
    PENDING,
    SOURCE,
    STATE_END,
    STATE_START,
    ActivityTracker,
)


def _observation(name, idle_seconds=0, **extra):
    observation = {"process_name": name, "idle_seconds": idle_seconds}
    observation.update(extra)
    return observation


@pytest.fixture
def storage(tmp_path):
    db = ActivityDatabase(tmp_path / "test.db")
    db.initialize()
    yield db
    db.close()


def _tracker(storage, observations, heartbeat_interval=60, idle_threshold=60, clock=None):
    return ActivityTracker(
        observer=FakeObserver(observations),
        storage=storage,
        clock=clock or FakeClock(),
        heartbeat_interval=heartbeat_interval,
        idle_threshold=idle_threshold,
    )


def test_first_observation_records_state_start(storage):
    tracker = _tracker(storage, [_observation("Code.exe", process_id=1)])

    events = tracker.observe()

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == STATE_START
    assert event["application"] == "code.exe"
    assert event["source"] == SOURCE
    assert event["sync_status"] == PENDING
    assert event["duration_seconds"] == 0
    assert event["state_id"]
    assert storage.count_events() == 1


def test_same_application_before_interval_records_nothing(storage):
    tracker = _tracker(storage, [_observation("Code.exe")])
    tracker.observe()

    events = tracker.observe()

    assert events == []
    assert storage.count_events() == 1


def test_same_application_after_interval_records_heartbeat(storage):
    clock = FakeClock()
    tracker = _tracker(
        storage,
        [_observation("Code.exe"), _observation("Code.exe")],
        clock=clock,
    )
    start_events = tracker.observe()

    clock.advance(60)
    events = tracker.observe()

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == HEARTBEAT
    assert event["application"] == "code.exe"
    assert event["duration_seconds"] == 60
    assert event["state_id"] == start_events[0]["state_id"]


def test_multiple_heartbeats_share_state_id(storage):
    clock = FakeClock()
    tracker = _tracker(
        storage,
        [_observation("Code.exe")] * 4,
        clock=clock,
    )
    tracker.observe()
    clock.advance(60)
    tracker.observe()
    clock.advance(60)
    tracker.observe()
    clock.advance(60)
    tracker.observe()

    events = storage.get_events()
    assert [e["event_type"] for e in events] == [
        STATE_START,
        HEARTBEAT,
        HEARTBEAT,
        HEARTBEAT,
    ]
    assert len({e["state_id"] for e in events}) == 1


def test_application_change_ends_and_starts_new_state(storage):
    clock = FakeClock()
    tracker = _tracker(
        storage,
        [_observation("Code.exe"), _observation("Chrome.exe")],
        clock=clock,
    )
    start_events = tracker.observe()

    clock.advance(70)
    events = tracker.observe()

    assert [e["event_type"] for e in events] == [STATE_END, STATE_START]
    end_event, start_event = events
    assert end_event["application"] == "code.exe"
    assert end_event["duration_seconds"] == 70
    assert end_event["state_id"] == start_events[0]["state_id"]
    assert start_event["application"] == "chrome.exe"
    assert start_event["duration_seconds"] == 0
    assert start_event["state_id"] != end_event["state_id"]


def test_none_observation_records_nothing_and_preserves_state(storage):
    clock = FakeClock()
    tracker = _tracker(
        storage,
        [_observation("Code.exe"), None, _observation("Code.exe")],
        clock=clock,
    )
    start_events = tracker.observe()

    events = tracker.observe()
    assert events == []
    assert storage.count_events() == 1

    clock.advance(60)
    events = tracker.observe()
    assert events[0]["event_type"] == HEARTBEAT
    assert events[0]["state_id"] == start_events[0]["state_id"]


def test_restart_creates_new_state_id(storage):
    first = _tracker(storage, [_observation("Code.exe")]).observe()

    restarted = _tracker(storage, [_observation("Code.exe")])
    events = restarted.observe()

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == STATE_START
    assert event["application"] == "code.exe"
    assert event["state_id"] != first[0]["state_id"]
    # No fabricated STATE_END before the new STATE_START.
    assert [e["event_type"] for e in storage.get_events()] == [
        STATE_START,
        STATE_START,
    ]


def test_active_to_idle_transition(storage):
    clock = FakeClock()
    tracker = _tracker(
        storage,
        [_observation("Code.exe"), _observation("Code.exe", idle_seconds=60)],
        clock=clock,
    )
    start_events = tracker.observe()
    clock.advance(60)
    events = tracker.observe()

    assert [e["event_type"] for e in events] == [STATE_END, STATE_START]
    end_event, idle_event = events
    assert end_event["application"] == "code.exe"
    assert end_event["duration_seconds"] == 0
    assert end_event["state_id"] == start_events[0]["state_id"]
    assert idle_event["application"] == "idle"
    assert idle_event["duration_seconds"] == 60
    assert idle_event["state_id"] != end_event["state_id"]


def test_idle_heartbeats_share_state_id(storage):
    clock = FakeClock()
    tracker = _tracker(
        storage,
        [
            _observation("Code.exe"),
            _observation("Code.exe", idle_seconds=60),
            _observation("Code.exe", idle_seconds=120),
            _observation("Code.exe", idle_seconds=180),
        ],
        clock=clock,
    )
    tracker.observe()
    clock.advance(60)
    tracker.observe()  # -> idle
    clock.advance(60)
    idle_heartbeat = tracker.observe()
    clock.advance(60)
    tracker.observe()

    idle_events = [
        e for e in storage.get_events() if e["application"] == "idle"
    ]
    assert [e["event_type"] for e in idle_events] == [
        STATE_START,
        HEARTBEAT,
        HEARTBEAT,
    ]
    assert len({e["state_id"] for e in idle_events}) == 1
    assert idle_heartbeat[0]["duration_seconds"] == 60


def test_idle_to_active_transition(storage):
    clock = FakeClock()
    tracker = _tracker(
        storage,
        [
            _observation("Code.exe"),
            _observation("Code.exe", idle_seconds=60),
            _observation("Code.exe"),
        ],
        clock=clock,
    )
    tracker.observe()
    clock.advance(60)
    idle_start = tracker.observe()
    clock.advance(60)
    events = tracker.observe()

    assert [e["event_type"] for e in events] == [STATE_END, STATE_START]
    idle_end, app_start = events
    assert idle_end["application"] == "idle"
    assert idle_end["duration_seconds"] == 60
    assert idle_end["state_id"] == idle_start[1]["state_id"]
    assert app_start["application"] == "code.exe"
    assert app_start["duration_seconds"] == 0
    assert app_start["state_id"] != idle_end["state_id"]


def test_idle_below_threshold_is_not_idle(storage):
    clock = FakeClock()
    tracker = _tracker(
        storage,
        [_observation("Code.exe"), _observation("Code.exe", idle_seconds=59)],
        clock=clock,
    )
    tracker.observe()
    clock.advance(60)
    events = tracker.observe()

    assert len(events) == 1
    assert events[0]["event_type"] == HEARTBEAT
    assert events[0]["application"] == "code.exe"


def test_startup_while_idle(storage):
    tracker = _tracker(storage, [_observation("Code.exe", idle_seconds=300)])

    events = tracker.observe()

    assert len(events) == 1
    assert events[0]["application"] == "idle"
    assert events[0]["duration_seconds"] == 300
    assert events[0]["state_id"]


def test_app_change_while_idle_ignored(storage):
    clock = FakeClock()
    tracker = _tracker(
        storage,
        [
            _observation("Code.exe"),
            _observation("Code.exe", idle_seconds=60),
            _observation("Chrome.exe", idle_seconds=120),
        ],
        clock=clock,
    )
    tracker.observe()
    clock.advance(60)
    tracker.observe()  # -> idle
    clock.advance(60)
    events = tracker.observe()  # app switched, but still idle

    assert len(events) == 1
    assert events[0]["event_type"] == HEARTBEAT
    assert events[0]["application"] == "idle"


def test_active_no_foreground_window_skips(storage):
    tracker = _tracker(
        storage,
        [{"process_name": None, "idle_seconds": 5}],
    )

    assert tracker.observe() == []
