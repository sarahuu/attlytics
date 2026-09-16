from uuid import uuid4

from tests.factories import (
    FakeDevice,
    api_url,
    client,
    heartbeat_payload as payload,
    ingest_api as api,
    unauthenticated,
)

INGEST_URL = api_url("/heartbeats")


# --- device authentication --------------------------------------------------


def test_ingest_without_a_key_is_rejected(unauthenticated):
    response = client.post(INGEST_URL, json=[payload()])

    assert response.status_code == 401


def test_ingest_is_attributed_to_the_authenticated_device(api):
    device = FakeDevice()
    recorder = api(device=device)

    response = client.post(INGEST_URL, json=[payload()])

    assert response.status_code == 201
    assert recorder.calls[0][1] is device


def test_client_supplied_owner_fields_never_reach_the_service(api):
    recorder = api()

    response = client.post(
        INGEST_URL,
        json=[payload(device_id=str(uuid4()), user_id=str(uuid4()))],
    )

    assert response.status_code == 201
    sent = recorder.payloads[0].model_dump()
    assert "device_id" not in sent
    assert "user_id" not in sent


# --- accepted payloads ------------------------------------------------------


def test_valid_batch_returns_the_service_counts(api):
    api(result=(2, 3))

    response = client.post(INGEST_URL, json=[payload(), payload()])

    assert response.status_code == 201
    assert response.json() == {"received": 2, "skipped": 3}


def test_events_keep_their_order(api):
    recorder = api()
    local_ids = [str(uuid4()) for _ in range(3)]

    client.post(INGEST_URL, json=[payload(local_id=value) for value in local_ids])

    assert [str(item.local_id) for item in recorder.payloads] == local_ids


def test_empty_batch_is_accepted(api):
    recorder = api(result=(0, 0))

    response = client.post(INGEST_URL, json=[])

    assert response.status_code == 201
    assert response.json() == {"received": 0, "skipped": 0}
    assert recorder.payloads == []


def test_optional_fields_default(api):
    recorder = api()

    client.post(
        INGEST_URL,
        json=[
            {
                "local_id": str(uuid4()),
                "state_id": str(uuid4()),
                "application": "code",
                "timestamp": "2026-09-16T09:00:00Z",
            }
        ],
    )

    sent = recorder.payloads[0]
    assert sent.source.value == "os"
    assert sent.event_type.value == "HEARTBEAT"


def test_event_metadata_is_accepted(api):
    recorder = api()

    response = client.post(
        INGEST_URL,
        json=[
            payload(
                event_type="STATE_END",
                duration_seconds=12.5,
                process_id=4242,
                window_title="main.py - attlytics - Visual Studio Code",
            )
        ],
    )

    assert response.status_code == 201
    sent = recorder.payloads[0]
    assert sent.event_type.value == "STATE_END"
    assert sent.duration_seconds == 12.5
    assert sent.process_id == 4242
    assert sent.window_title.startswith("main.py")


# --- rejected payloads ------------------------------------------------------


def test_unknown_event_type_is_rejected(api):
    api()

    response = client.post(INGEST_URL, json=[payload(event_type="NOPE")])

    assert response.status_code == 422


def test_missing_local_id_is_rejected(api):
    api()

    body = payload()
    del body["local_id"]

    response = client.post(INGEST_URL, json=[body])

    assert response.status_code == 422


def test_non_uuid_local_id_is_rejected(api):
    api()

    response = client.post(INGEST_URL, json=[payload(local_id="1234")])

    assert response.status_code == 422


def test_unparsable_timestamp_is_rejected(api):
    api()

    response = client.post(INGEST_URL, json=[payload(timestamp="yesterday")])

    assert response.status_code == 422


def test_invalid_entry_rejects_the_whole_batch(api):
    recorder = api()

    response = client.post(INGEST_URL, json=[payload(), {"application": "code"}])

    assert response.status_code == 422
    assert recorder.calls == []


def test_offsetless_timestamp_is_rejected(api):
    api()

    response = client.post(
        INGEST_URL, json=[payload(timestamp="2026-09-16T09:00:00")]
    )

    assert response.status_code == 422


def test_non_utc_offset_is_normalised_to_utc(api):
    recorder = api()

    response = client.post(
        INGEST_URL, json=[payload(timestamp="2026-09-16T10:00:00+01:00")]
    )

    assert response.status_code == 201
    assert recorder.payloads[0].timestamp.isoformat() == "2026-09-16T09:00:00+00:00"
