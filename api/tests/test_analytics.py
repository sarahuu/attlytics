from datetime import timedelta
from uuid import uuid4

from tests.factories import (
    NOW,
    OTHER_USER_ID,
    USER_ID,
    FakeApplicationStat,
    FakeSessionRow,
    FakeSummary,
    RecordingRepo,
    api_url,
    client,
    session_api as api,
    unauthenticated,
)

SESSIONS_URL = api_url("/sessions")
SUMMARY_URL = api_url("/stats/summary")
APPLICATIONS_URL = api_url("/stats/applications")


# --- authentication ---------------------------------------------------------


def test_requests_without_a_token_are_rejected(unauthenticated):
    response = client.get(SESSIONS_URL)

    assert response.status_code == 401


# --- owner scoping ----------------------------------------------------------


def test_session_list_is_scoped_to_the_logged_in_user(api):
    repo = api(RecordingRepo(rows=[]))

    response = client.get(SESSIONS_URL)

    assert response.status_code == 200
    assert repo.owner_ids == [USER_ID]


def test_session_list_uses_a_different_owner_for_a_different_user(api):
    repo = api(RecordingRepo(rows=[]), user_id=OTHER_USER_ID)

    client.get(SESSIONS_URL)

    assert repo.owner_ids == [OTHER_USER_ID]
    assert USER_ID not in repo.owner_ids


def test_session_detail_is_scoped_to_the_logged_in_user(api):
    session_id = uuid4()
    repo = api(RecordingRepo(session=FakeSessionRow(session_id=session_id)))

    response = client.get(f"{SESSIONS_URL}/{session_id}")

    assert response.status_code == 200
    assert repo.owner_ids == [USER_ID]
    assert repo.session_ids == [session_id]


def test_summary_is_scoped_to_the_logged_in_user(api):
    repo = api(RecordingRepo(summary=FakeSummary()))

    response = client.get(SUMMARY_URL)

    assert response.status_code == 200
    assert repo.owner_ids == [USER_ID]


def test_applications_are_scoped_to_the_logged_in_user(api):
    repo = api(RecordingRepo(rows=[FakeApplicationStat("code", 30.0)], total=100.0))

    response = client.get(APPLICATIONS_URL)

    assert response.status_code == 200
    assert repo.owner_ids == [USER_ID]


# --- response shapes --------------------------------------------------------


def test_session_list_serialises_the_row(api):
    api(RecordingRepo(rows=[FakeSessionRow(application="code")]))

    body = client.get(SESSIONS_URL).json()

    assert len(body["items"]) == 1
    assert body["items"][0]["application"] == "code"
    assert body["items"][0]["source"] == "os"
    assert body["next_cursor"] is None


def test_unknown_session_returns_404(api):
    api(RecordingRepo(session=None))

    response = client.get(f"{SESSIONS_URL}/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"


def test_non_uuid_session_id_returns_422(api):
    api(RecordingRepo())

    response = client.get(f"{SESSIONS_URL}/not-a-uuid")

    assert response.status_code == 422


def test_summary_reports_computed_average(api):
    api(RecordingRepo(summary=FakeSummary(total_seconds=3600.0, active_days=2)))

    body = client.get(SUMMARY_URL).json()

    assert body["total_seconds"] == 3600.0
    assert body["average_seconds_per_active_day"] == 1800.0
    assert body["active_days"] == 2


def test_application_share_is_returned(api):
    api(
        RecordingRepo(
            rows=[FakeApplicationStat("code", 30.0), FakeApplicationStat("chat", 10.0)],
            total=100.0,
        )
    )

    body = client.get(APPLICATIONS_URL).json()

    assert [row["share_percent"] for row in body] == [30.0, 10.0]


# --- parameters -------------------------------------------------------------


def test_timezone_reaches_the_query_layer(api):
    repo = api(RecordingRepo(summary=FakeSummary()))

    client.get(SUMMARY_URL, params={"tz": "Europe/London"})

    assert repo.tz == "Europe/London"


def test_unknown_timezone_is_rejected(api):
    api(RecordingRepo(summary=FakeSummary()))

    response = client.get(SUMMARY_URL, params={"tz": "Mars/Olympus"})

    assert response.status_code == 422


def test_inverted_window_is_rejected(api):
    api(RecordingRepo(rows=[]))

    response = client.get(
        SESSIONS_URL,
        params={
            "start": "2026-09-16T12:00:00Z",
            "end": "2026-09-16T11:00:00Z",
        },
    )

    assert response.status_code == 422


def test_oversized_window_is_rejected(api):
    api(RecordingRepo(rows=[]))

    response = client.get(
        SESSIONS_URL,
        params={
            "start": "2025-01-01T00:00:00Z",
            "end": "2026-09-16T00:00:00Z",
        },
    )

    assert response.status_code == 422


def test_garbage_cursor_is_rejected(api):
    api(RecordingRepo(rows=[]))

    response = client.get(SESSIONS_URL, params={"cursor": "not-a-cursor"})

    assert response.status_code == 422


def test_limit_upper_bound_is_enforced(api):
    api(RecordingRepo(rows=[]))

    response = client.get(SESSIONS_URL, params={"limit": 5000})

    assert response.status_code == 422


# --- paging -----------------------------------------------------------------


def test_full_page_returns_a_usable_cursor(api):
    rows = [FakeSessionRow(start_time=NOW - timedelta(minutes=index)) for index in range(3)]
    repo = api(RecordingRepo(rows=rows))

    body = client.get(SESSIONS_URL, params={"limit": 2}).json()

    assert len(body["items"]) == 2
    assert body["next_cursor"]

    follow_up = client.get(
        SESSIONS_URL, params={"limit": 2, "cursor": body["next_cursor"]}
    )

    assert follow_up.status_code == 200
    assert repo.list_kwargs["cursor"] == (rows[1].start_time, rows[1].id)


def test_filters_are_passed_through(api):
    repo = api(RecordingRepo(rows=[]))
    device_id = uuid4()

    client.get(
        SESSIONS_URL,
        params={"application": "code", "device_id": str(device_id), "source": "os"},
    )

    assert repo.list_kwargs["application"] == "code"
    assert repo.list_kwargs["device_id"] == device_id
    assert repo.list_kwargs["source"] == "os"
