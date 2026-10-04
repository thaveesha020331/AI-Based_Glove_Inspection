from flask import Blueprint, jsonify

overview_bp = Blueprint("overview", __name__)


@overview_bp.get("/overview")
def overview():
    return jsonify({"dataMode": "demo", "message": "Overview API contract is ready."})
