import json

import pytest

from app import create_app
from app.services.live_orientation import LiveOrientationWorker


class FakeOrientationWorker:
    def __init__(self):
        self.state = "stopped"
        self.mode = None
        self.exposure = -2

    def snapshot(self):
        return {
            "state": self.state,
            "mode": self.mode,
            "running": self.state in {"starting", "running"},
            "error": None,
            "stable_prediction": "LeftHand" if self.state == "running" else None,
            "camera_exposure": self.exposure,
            "camera_actual_exposure": self.exposure if self.state == "running" else None,
        }

    def start(self, mode="orientation"):
        if mode not in {"orientation", "defect"}:
            raise ValueError("mode must be orientation or defect.")
        self.mode = mode
        self.state = "running"
        return self.snapshot()

    def stop(self):
        self.state = "stopped"
        return self.snapshot()

    def configure_camera(self, exposure):
        exposure = float(exposure)
        if exposure < -7 or exposure > -2:
            raise ValueError("exposure must be between -7 and -2.")
        self.exposure = exposure
        return self.snapshot()

    def wait_for_update(self, _version, timeout=1.0):
        return self.snapshot(), 1

    def wait_for_frame(self, _previous, timeout=1.0):
        return b"fake-jpeg"

    def wait_for_orientation_frame(self, _previous, timeout=1.0):
        return b"orientation-only-jpeg"


@pytest.fixture()
def client():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    app.extensions["live_orientation_worker"] = FakeOrientationWorker()
    return app.test_client()


def test_orientation_can_be_started_and_stopped(client):
    initial = client.get("/api/v1/orientation/live")
    started = client.post("/api/v1/orientation/live/start")
    stopped = client.post("/api/v1/orientation/live/stop")

    assert initial.get_json()["data"]["state"] == "stopped"
    assert started.status_code == 202
    assert started.get_json()["data"]["mode"] == "orientation"
    assert started.get_json()["data"]["stable_prediction"] == "LeftHand"
    assert stopped.get_json()["data"]["state"] == "stopped"


def test_defect_mode_can_be_started(client):
    started = client.post(
        "/api/v1/orientation/live/start", json={"mode": "defect"}
    )
    invalid = client.post(
        "/api/v1/orientation/live/start", json={"mode": "both"}
    )

    assert started.status_code == 202
    assert started.get_json()["data"]["mode"] == "defect"
    assert invalid.status_code == 400


def test_orientation_stream_emits_named_event(client):
    response = client.get("/api/v1/orientation/live/stream", buffered=False)
    first_event = next(response.response).decode("utf-8")
    response.close()

    assert first_event.startswith("event: orientation\ndata: ")
    payload = json.loads(first_event.split("data: ", 1)[1])
    assert payload["state"] == "stopped"


def test_orientation_video_is_mjpeg(client):
    client.post("/api/v1/orientation/live/start")
    response = client.get("/api/v1/orientation/live/video", buffered=False)
    first_frame = next(response.response)
    response.close()

    assert response.mimetype == "multipart/x-mixed-replace"
    assert b"Content-Type: image/jpeg" in first_frame
    assert b"fake-jpeg" in first_frame


def test_orientation_only_video_is_mjpeg(client):
    client.post("/api/v1/orientation/live/start")
    response = client.get("/api/v1/orientation/live/orientation-video", buffered=False)
    first_frame = next(response.response)
    response.close()

    assert response.mimetype == "multipart/x-mixed-replace"
    assert b"orientation-only-jpeg" in first_frame


def test_camera_exposure_can_be_adjusted(client):
    updated = client.patch(
        "/api/v1/orientation/live/camera", json={"exposure": -3}
    )
    invalid = client.patch(
        "/api/v1/orientation/live/camera", json={"exposure": -1}
    )

    assert updated.status_code == 200
    assert updated.get_json()["data"]["camera_exposure"] == -3
    assert invalid.status_code == 400
    assert invalid.get_json()["error"]["code"] == "invalid_camera_setting"


def test_worker_reports_uncertain_after_analysis_without_stable_result(tmp_path):
    worker = LiveOrientationWorker(tmp_path / "model.pt", minimum_confidence=0.80)
    worker._state = "running"
    worker._frame_count = worker.smoothing_window

    snapshot = worker.snapshot()

    assert snapshot["decision_state"] == "uncertain"
    assert snapshot["minimum_confidence"] == 0.80
    assert snapshot["camera_auto_exposure"] is False
    assert snapshot["camera_auto_exposure_supported"] is None
    assert snapshot["camera_exposure"] == -2
    assert snapshot["camera_gain"] == 0
    assert snapshot["defective"] is False
    assert snapshot["defect_ready"] is False
