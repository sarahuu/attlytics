from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.dependencies import get_current_device, get_current_user
from app.db.session import get_db
from app.main import app
from app.services import analytics, heartbeats

API_PREFIX = get_settings().api_v1_prefix
NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

USER_ID = uuid4()
OTHER_USER_ID = uuid4()
DEVICE_ID = uuid4()

client = TestClient(app)


def api_url(path: str) -> str:
    """Build a versioned URL, so tests never hardcode the prefix."""
    return f"{API_PREFIX}{path}"


async def override_db():
    yield None


# --- identity ---------------------------------------------------------------


class FakeUser:
    def __init__(self, user_id=None):
        self.id = user_id or USER_ID


class FakeDevice:
    def __init__(self, device_id=None, user_id=None):
        self.id = device_id or DEVICE_ID
        self.user_id = user_id or USER_ID
        self.is_active = True


# --- session rows and aggregates -------------------------------------------


class FakeSessionRow:
    """A Session ORM stand-in carrying every field SessionOut needs."""

    def __init__(self, session_id=None, application="code", start_time=None):
        self.id = session_id or uuid4()
        self.device_id = uuid4()
        self.state_id = uuid4()
        self.source = "os"
        self.application = application
        self.start_time = start_time or NOW
        self.end_time = None
        self.duration_seconds = 60.0
        self.created_at = NOW
        self.updated_at = NOW


class FakeSummary:
    def __init__(self, total_seconds=3600.0, active_days=2, longest_seconds=1800.0):
        self.total_seconds = total_seconds
        self.session_count = 4
        self.active_days = active_days
        self.longest_session_seconds = longest_seconds
        self.first_activity = NOW
        self.last_activity = NOW


class FakeApplicationStat:
    def __init__(self, application, total_seconds):
        self.application = application
        self.total_seconds = total_seconds
        self.session_count = 1


# --- recording doubles ------------------------------------------------------


class RecordingRepo:
    """A stand-in ActivityRepository that records the owner id it was given."""

    def __init__(self, rows=None, total=0.0, summary=None, session=None):
        self.rows = rows if rows is not None else []
        self.total = total
        self.summary = summary
        self.session = session
        self.owner_ids = []
        self.session_ids = []
        self.tz = None
        self.list_kwargs = None

    async def list_sessions(self, user_id, start, end, **kwargs):
        self.owner_ids.append(user_id)
        self.list_kwargs = kwargs
        return self.rows

    async def get_session(self, user_id, session_id):
        self.owner_ids.append(user_id)
        self.session_ids.append(session_id)
        return self.session

    async def summarize_sessions(self, user_id, start, end, tz, **kwargs):
        self.owner_ids.append(user_id)
        self.tz = tz
        return self.summary

    async def time_per_application(self, user_id, start, end, **kwargs):
        self.owner_ids.append(user_id)
        return self.rows

    async def total_duration(self, user_id, start, end, **kwargs):
        self.owner_ids.append(user_id)
        return self.total


class RecordingIngest:
    """A stand-in ingest service that keeps every argument it was handed."""

    def __init__(self, result=(1, 0)):
        self.result = result
        self.calls = []

    async def __call__(self, db, device, payloads):
        self.calls.append((db, device, payloads))
        return self.result

    @property
    def payloads(self):
        return self.calls[0][2]


def heartbeat_payload(**overrides):
    """A minimal valid ingest body; override any field per test."""
    body = {
        "local_id": str(uuid4()),
        "state_id": str(uuid4()),
        "application": "code",
        "timestamp": "2026-09-16T09:00:00Z",
    }
    body.update(overrides)
    return body


# --- fixtures ---------------------------------------------------------------


@pytest.fixture
def session_api(monkeypatch):
    """Point the read endpoints at a recording repo and a fixed logged-in user."""

    def configure(repo=None, user_id=USER_ID):
        repo = repo if repo is not None else RecordingRepo()
        monkeypatch.setattr(analytics, "ActivityRepository", lambda db: repo)

        async def override_user():
            return FakeUser(user_id)

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        return repo

    yield configure

    app.dependency_overrides.clear()


@pytest.fixture
def ingest_api(monkeypatch):
    """Point the ingest endpoint at a recording service and a fixed device."""

    def configure(result=(1, 0), device=None):
        recorder = RecordingIngest(result)
        monkeypatch.setattr(heartbeats, "ingest_heartbeats", recorder)

        async def override_device():
            return device or FakeDevice()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_device] = override_device
        return recorder

    yield configure

    app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated():
    """Leave the real auth dependency in place so it rejects the request."""
    app.dependency_overrides[get_db] = override_db

    yield

    app.dependency_overrides.clear()
