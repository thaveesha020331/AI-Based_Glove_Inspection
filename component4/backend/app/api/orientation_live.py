"""HTTP and streaming endpoints for live glove-orientation inference."""

import json

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context


orientation_live_bp = Blueprint("orientation_live", __name__)


def _worker():
    return current_app.extensions["live_orientation_worker"]


@orientation_live_bp.get("")
def status():
    return jsonify({"data": _worker().snapshot()})


@orientation_live_bp.post("/start")
def start():
    payload = request.get_json(silent=True) or {}
    try:
        snapshot = _worker().start(payload.get("mode", "orientation"))
    except ValueError as error:
        return jsonify({"error": {"code": "invalid_inference_mode", "message": str(error)}}), 400
    return jsonify({"data": snapshot}), 202


@orientation_live_bp.post("/stop")
def stop():
    return jsonify({"data": _worker().stop()})


@orientation_live_bp.patch("/camera")
def configure_camera():
    payload = request.get_json(silent=True) or {}
    try:
        snapshot = _worker().configure_camera(payload.get("exposure"))
    except ValueError as error:
        return jsonify({"error": {"code": "invalid_camera_setting", "message": str(error)}}), 400
    return jsonify({"data": snapshot})


@orientation_live_bp.get("/stream")
def stream():
    worker = _worker()

    @stream_with_context
    def events():
        version = -1
        while True:
            snapshot, version = worker.wait_for_update(version, timeout=1.0)
            payload = json.dumps(snapshot, separators=(",", ":"))
            yield f"event: orientation\ndata: {payload}\n\n"

    response = Response(events(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@orientation_live_bp.get("/video")
def video():
    worker = _worker()

    @stream_with_context
    def frames():
        previous = None
        while True:
            frame = worker.wait_for_frame(previous, timeout=1.0)
            if frame is not None and frame is not previous:
                previous = frame
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n\r\n" + frame + b"\r\n"
                )
            if not worker.snapshot()["running"]:
                return

    return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@orientation_live_bp.get("/orientation-video")
def orientation_video():
    worker = _worker()

    @stream_with_context
    def frames():
        previous = None
        while True:
            frame = worker.wait_for_orientation_frame(previous, timeout=1.0)
            if frame is not None and frame is not previous:
                previous = frame
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n\r\n" + frame + b"\r\n"
                )
            if not worker.snapshot()["running"]:
                return

    return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")
