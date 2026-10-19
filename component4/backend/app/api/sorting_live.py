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
    return snapshot


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

