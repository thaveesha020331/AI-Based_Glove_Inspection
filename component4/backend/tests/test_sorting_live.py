import json

import pytest

from app import create_app
from app.services.sorting_live import sorting_telemetry


@pytest.fixture()
def client():
    sorting_telemetry.reset()
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SORTING_TELEMETRY_STALE_SECONDS": 3,
    })
    yield app.test_client()
    sorting_telemetry.reset()


def test_live_status_waits_for_driver(client):
    result = client.get("/api/v1/sorting/live")

    assert result.status_code == 200
    assert result.get_json()["data"]["status"] == "waiting_for_driver"
    assert result.get_json()["data"]["online"] is False


def test_driver_status_is_normalized_and_returned(client):
    payload = {
        "type": "c3_status",
        "uptime_ms": 12500,
        "sensors": {
            "speed_s1": True,
            "speed_s2": False,
            "verify_v1": "detected",
            "verify_v2": 0,
        },
        "relays": {"relay1": 1, "relay2": 0, "relay3": False, "relay4": "off"},
    }

    accepted = client.post("/api/v1/sorting/live", json=payload)
    current = client.get("/api/v1/sorting/live").get_json()["data"]

    assert accepted.status_code == 202
    assert current["online"] is True
    assert current["sensors"]["speed_s1"] is True
    assert current["sensors"]["verify_v1"] is True
    assert current["relays"]["relay1"] is True
    assert current["received_at"]


def test_live_stream_emits_current_snapshot(client):
    response = client.get("/api/v1/sorting/stream", buffered=False)
    first_event = next(response.response).decode("utf-8")
    response.close()

    assert first_event.startswith("data: ")
    payload = json.loads(first_event.removeprefix("data: ").strip())
    assert payload["type"] == "c3_status"
    assert payload["driver"]["state"] == "disabled"


@pytest.mark.parametrize("payload", [None, {}, {"type": "wrong"}, {"type": "c3_status"}])
def test_invalid_driver_payload_is_rejected(client, payload):
    result = client.post("/api/v1/sorting/live", json=payload)

    assert result.status_code == 400
    assert result.get_json()["error"]["code"] == "validation_error"

