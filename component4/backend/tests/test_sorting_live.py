import json

import pytest

from app import create_app
from app.services.sorting_live import sorting_telemetry
from app.services.sorting_control import SortingControlService


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


def test_local_dashboard_can_control_light_and_expected_orientation(client):
    commands = []

    def send(command):
        commands.append(command)
        return True

    client.application.extensions["sorting_control"] = SortingControlService(send)

    configured = client.patch(
        "/api/v1/sorting/control",
        json={"expected_orientation": "RightHand"},
    )
    light = client.post("/api/v1/sorting/control/light", json={"on": True})

    assert configured.status_code == 200
    assert configured.get_json()["data"]["expected_orientation"] == "RightHand"
    assert light.status_code == 200
    assert commands == ["CAMERA_LIGHT_ON"]


def test_hardware_mutation_is_rejected_for_non_local_client(client):
    result = client.post(
        "/api/v1/sorting/control/light",
        json={"on": True},
        environ_base={"REMOTE_ADDR": "192.0.2.5"},
    )

    assert result.status_code == 403
    assert result.get_json()["error"]["code"] == "local_control_only"


def test_speed_sync_uses_s1_then_s2_rising_edges(client):
    def status(uptime_ms, s1=False, s2=False):
        return {
            "type": "c3_status",
            "uptime_ms": uptime_ms,
            "sensors": {
                "speed_s1": s1,
                "speed_s2": s2,
                "verify_v1": False,
                "verify_v2": False,
            },
            "relays": {
                "relay1": False,
                "relay2": False,
                "relay3": False,
                "relay4": False,
            },
        }

    client.post("/api/v1/sorting/live", json=status(500))
    armed = client.post("/api/v1/sorting/speed-sync", json={"distance_cm": 100})
    client.post("/api/v1/sorting/live", json=status(1000, s1=True))
    client.post("/api/v1/sorting/live", json=status(1500))
    client.post("/api/v1/sorting/live", json=status(3000, s2=True))
    result = client.get("/api/v1/sorting/live").get_json()["data"]["speed_sync"]

    assert armed.status_code == 202
    assert result["state"] == "complete"
    assert result["elapsed_ms"] == 2000
    assert result["speed_mps"] == 0.5
    assert result["speed_cmps"] == 50.0


@pytest.mark.parametrize("distance", [None, 0, -1, 10001, "invalid"])
def test_speed_sync_rejects_invalid_distance(client, distance):
    result = client.post(
        "/api/v1/sorting/speed-sync", json={"distance_cm": distance}
    )

    assert result.status_code == 400
    assert result.get_json()["error"]["code"] == "validation_error"

