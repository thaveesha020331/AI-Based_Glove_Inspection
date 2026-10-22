from flask import Blueprint, current_app, jsonify
from pathlib import Path
from sqlalchemy import text

from app import db
from app.services.defect_detection import DefectDetector

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    try:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        current_app.logger.exception("Database health check failed")
        database = "unavailable"
    detector_status = DefectDetector(current_app.config["DEFECT_MODEL_PATH"]).status()
    return jsonify({
        "status": "ok" if database == "ok" else "degraded",
        "service": "gloveiq-api",
        "database": database,
        "model_available": detector_status["ready"],
        "model": detector_status,
    })
