import json

import pytest

from app import create_app
from app.services.live_orientation import LiveOrientationWorker


class FakeOrientationWorker:
    def __init__(self):
        self.state = "stopped"

    def snapshot(self):
        return {
            "state": self.state,
            "running": self.state in {"starting", "running"},
            "error": None,
            "stable_prediction": "LeftHand" if self.state == "running" else None,
        }

    def start(self):
        self.state = "running"
        return self.snapshot()

    def stop(self):
        self.state = "stopped"
        return self.snapshot()

    def wait_for_update(self, _version, timeout=1.0):
        return self.snapshot(), 1

    def wait_for_frame(self, _previous, timeout=1.0):
        return b"fake-jpeg"


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
    assert started.get_json()["data"]["stable_prediction"] == "LeftHand"
    assert stopped.get_json()["data"]["state"] == "stopped"


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


def test_worker_reports_uncertain_after_analysis_without_stable_result(tmp_path):
    worker = LiveOrientationWorker(tmp_path / "model.pt", minimum_confidence=0.80)
    worker._state = "running"
    worker._frame_count = worker.smoothing_window

    snapshot = worker.snapshot()

    assert snapshot["decision_state"] == "uncertain"
    assert snapshot["minimum_confidence"] == 0.80
