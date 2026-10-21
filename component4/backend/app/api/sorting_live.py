"""Local serial-driver bridge endpoints for Component 3 telemetry."""

import json

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from app.services.sorting_live import sorting_telemetry

sorting_live_bp = Blueprint("sorting_live", __name__)


def response(data, status=200):
    return jsonify({"data": data}), status


def _with_driver_status(snapshot, manager, config):
    snapshot["driver"] = manager.status() if manager else {
        "running": False,
        "state": "disabled",
        "port": config.get("COMPONENT3_SERIAL_PORT"),
        "baud_rate": config.get("COMPONENT3_BAUD_RATE"),
        "last_error": None,
    }
    control = current_app.extensions.get("sorting_control")
    snapshot["control"] = control.snapshot() if control else None
    return snapshot


def _control():
    return current_app.extensions["sorting_control"]


def _local_control_denied():
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return jsonify({
            "error": {
                "code": "local_control_only",
                "message": "Hardware controls are available only from the backend computer.",
            }
        }), 403
    return None


@sorting_live_bp.get("/live")
def live_status():
    stale_seconds = current_app.config["SORTING_TELEMETRY_STALE_SECONDS"]
    snapshot = sorting_telemetry.snapshot(stale_seconds)
    manager = current_app.extensions.get("component3_serial_driver")
    return response(_with_driver_status(snapshot, manager, current_app.config))


@sorting_live_bp.get("/stream")
def live_stream():
    stale_seconds = current_app.config["SORTING_TELEMETRY_STALE_SECONDS"]
    manager = current_app.extensions.get("component3_serial_driver")
    config = dict(current_app.config)

    @stream_with_context
    def events():
        version = -1
        while True:
            snapshot, version = sorting_telemetry.wait_for_update(
                version, stale_seconds, timeout=1.0
            )
            data = _with_driver_status(snapshot, manager, config)
            yield f"data: {json.dumps(data, separators=(',', ':'))}\n\n"

    return Response(
        events(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@sorting_live_bp.post("/live")
def ingest_live_status():
    try:
        snapshot = sorting_telemetry.update(request.get_json(silent=True))
        return response(snapshot, 202)
    except ValueError as exc:
        return jsonify({"error": {"code": "validation_error", "message": str(exc)}}), 400


@sorting_live_bp.get("/control")
def control_status():
    return response(_control().snapshot())


@sorting_live_bp.post("/speed-sync")
def start_speed_sync():
    denied = _local_control_denied()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        return response(
            sorting_telemetry.arm_speed_sync(payload.get("distance_cm")),
            202,
        )
    except ValueError as exc:
        return jsonify({"error": {"code": "validation_error", "message": str(exc)}}), 400


@sorting_live_bp.patch("/control")
def configure_control():
    denied = _local_control_denied()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        return response(_control().configure(
            expected_orientation=payload.get("expected_orientation"),
            automatic_enabled=payload.get("automatic_enabled"),
        ))
    except ValueError as exc:
        return jsonify({"error": {"code": "validation_error", "message": str(exc)}}), 400


@sorting_live_bp.post("/control/light")
def camera_light():
    denied = _local_control_denied()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        data = _control().set_camera_light(payload.get("on"))
        return response(data, 200 if data["last_error"] is None else 503)
    except ValueError as exc:
        return jsonify({"error": {"code": "validation_error", "message": str(exc)}}), 400


@sorting_live_bp.post("/control/warning/reset")
def reset_warning():
    denied = _local_control_denied()
    if denied:
        return denied
    data = _control().reset_warning()
    return response(data, 200 if data["last_error"] is None else 503)


@sorting_live_bp.post("/control/decision")
def sorting_decision():
    """Accept one validated final glove decision from a local detector."""
    denied = _local_control_denied()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        data = _control().process_decision(
            orientation=payload.get("orientation"),
            defective=payload.get("defective", False),
            source=payload.get("source", "local_detector"),
        )
        queued = data["last_action"].get("command_queued", True) if data["last_action"] else True
        return response(data, 202 if queued else 503)
    except ValueError as exc:
        return jsonify({"error": {"code": "validation_error", "message": str(exc)}}), 400

