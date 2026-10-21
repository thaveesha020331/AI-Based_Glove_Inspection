import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
migrate = Migrate()


def create_app(test_config: dict | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "development-only-change-me"),
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL", "sqlite:///gloveiq-dev.db"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=int(os.getenv("MAX_UPLOAD_BYTES", 5 * 1024 * 1024)),
        FRONTEND_ORIGIN=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        PREDICTIVE_MODEL_DIR=os.getenv("PREDICTIVE_MODEL_DIR"),
        QUALITY_REJECTION_THRESHOLD=float(os.getenv("QUALITY_REJECTION_THRESHOLD", "5")),
        REJECT_GRADE_THRESHOLD=float(os.getenv("REJECT_GRADE_THRESHOLD", "5")),
        RISK_LOW_PROBABILITY=float(os.getenv("RISK_LOW_PROBABILITY", "0.33")),
        RISK_HIGH_PROBABILITY=float(os.getenv("RISK_HIGH_PROBABILITY", "0.66")),
        PREDICTIVE_RANDOM_STATE=int(os.getenv("PREDICTIVE_RANDOM_STATE", "42")),
        PREDICTIVE_N_ESTIMATORS=int(os.getenv("PREDICTIVE_N_ESTIMATORS", "300")),
        PREDICTIVE_MIN_RECORDS=int(os.getenv("PREDICTIVE_MIN_RECORDS", "8")),
        SORTING_TELEMETRY_STALE_SECONDS=float(
            os.getenv("SORTING_TELEMETRY_STALE_SECONDS", "1")
        ),
        COMPONENT3_DRIVER_ENABLED=os.getenv(
            "COMPONENT3_DRIVER_ENABLED", "true"
        ).strip().casefold() in {"1", "true", "yes", "on"},
        COMPONENT3_SERIAL_PORT=os.getenv("COMPONENT3_SERIAL_PORT", "COM7"),
        COMPONENT3_BAUD_RATE=int(os.getenv("COMPONENT3_BAUD_RATE", "115200")),
        COMPONENT3_DRIVER_PATH=os.getenv(
            "COMPONENT3_DRIVER_PATH",
            str(Path(app.root_path).parents[2] / "Drivers" / "interface.py"),
        ),
        ORIENTATION_MODEL_PATH=os.getenv(
            "ORIENTATION_MODEL_PATH",
            str(
                Path(app.root_path).parent
                / "ml"
                / "quality_detection"
                / "weight"
                / "mobilenet_v2_classifier.torchscript.pt"
            ),
        ),
        ORIENTATION_CAMERA_INDEX=int(os.getenv("ORIENTATION_CAMERA_INDEX", "0")),
        CAMERA_AUTO_EXPOSURE=os.getenv(
            "CAMERA_AUTO_EXPOSURE", "true"
        ).strip().casefold() in {"1", "true", "yes", "on"},
        ORIENTATION_MIN_CONFIDENCE=float(
            os.getenv("ORIENTATION_MIN_CONFIDENCE", "0.80")
        ),
        ORIENTATION_SMOOTHING_WINDOW=int(
            os.getenv("ORIENTATION_SMOOTHING_WINDOW", "7")
        ),
        ORIENTATION_CLEAR_AFTER_FRAMES=int(
            os.getenv("ORIENTATION_CLEAR_AFTER_FRAMES", "4")
        ),
        DEFECT_MODEL_PATH=os.getenv(
            "DEFECT_MODEL_PATH",
            str(
                Path(app.root_path).parent
                / "ml"
                / "defect_detection"
                / "weight"
                / "best.pt"
            ),
        ),
        DEFECT_MIN_CONFIDENCE=float(os.getenv("DEFECT_MIN_CONFIDENCE", "0.50")),
        DEFECT_IMAGE_SIZE=int(os.getenv("DEFECT_IMAGE_SIZE", "640")),
        DEFECT_INFERENCE_INTERVAL=int(os.getenv("DEFECT_INFERENCE_INTERVAL", "2")),
        SORTING_EXPECTED_ORIENTATION=os.getenv(
            "SORTING_EXPECTED_ORIENTATION", "LeftHand"
        ),
        SORTING_WARNING_THRESHOLD=int(
            os.getenv("SORTING_WARNING_THRESHOLD", "3")
        ),
    )
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}})

    from app.api.v1 import api_v1_bp
    from app.api.health import health_bp
    from app.api.sorting_live import sorting_live_bp
    from app.api.orientation_live import orientation_live_bp
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(sorting_live_bp, url_prefix="/api/v1/sorting")
    app.register_blueprint(orientation_live_bp, url_prefix="/api/v1/orientation/live")

    from app.services.live_orientation import LiveOrientationWorker
    from app.services.sorting_control import SortingControlService

    def send_sorting_command(command):
        manager = app.extensions.get("component3_serial_driver")
        if manager is None:
            raise RuntimeError("Component 3 serial driver is disabled.")
        return manager.send_command(command)

    sorting_control = SortingControlService(
        command_sender=send_sorting_command,
        expected_orientation=app.config["SORTING_EXPECTED_ORIENTATION"],
        warning_threshold=app.config["SORTING_WARNING_THRESHOLD"],
    )
    app.extensions["sorting_control"] = sorting_control

    app.extensions["live_orientation_worker"] = LiveOrientationWorker(
        model_path=app.config["ORIENTATION_MODEL_PATH"],
        camera_index=app.config["ORIENTATION_CAMERA_INDEX"],
        camera_auto_exposure=app.config["CAMERA_AUTO_EXPOSURE"],
        smoothing_window=app.config["ORIENTATION_SMOOTHING_WINDOW"],
        minimum_confidence=app.config["ORIENTATION_MIN_CONFIDENCE"],
        clear_after_frames=app.config["ORIENTATION_CLEAR_AFTER_FRAMES"],
        defect_model_path=app.config["DEFECT_MODEL_PATH"],
        defect_min_confidence=app.config["DEFECT_MIN_CONFIDENCE"],
        defect_image_size=app.config["DEFECT_IMAGE_SIZE"],
        defect_inference_interval=app.config["DEFECT_INFERENCE_INTERVAL"],
        on_inspection=lambda orientation, orientation_confidence, defective, defect_category, defect_confidence: sorting_control.process_decision(
            orientation=orientation,
            defective=defective,
            source=(
                f"vision:orientation={orientation_confidence:.4f};"
                f"defect={defect_category or 'none'};"
                f"defect_confidence={defect_confidence or 0:.4f}"
            ),
        ),
    )

    if app.config["COMPONENT3_DRIVER_ENABLED"] and not app.config.get("TESTING"):
        from app.services.serial_driver import SerialDriverManager

        driver_manager = SerialDriverManager(
            app.config["COMPONENT3_DRIVER_PATH"],
            app.config["COMPONENT3_SERIAL_PORT"],
            app.config["COMPONENT3_BAUD_RATE"],
        )
        app.extensions["component3_serial_driver"] = driver_manager

        # The Werkzeug debug reloader imports the app once in its parent and
        # again in the serving child. Start only in the serving process so two
        # readers never compete for the same COM port.
        if not app.debug or os.getenv("WERKZEUG_RUN_MAIN") == "true":
            driver_manager.ensure_started()

        @app.before_request
        def ensure_component3_driver_started():
            driver_manager.ensure_started()

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify({"error": {"code": "payload_too_large", "message": "Upload exceeds the configured size limit."}}), 413

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": {"code": "not_found", "message": "Resource not found."}}), 404

    @app.errorhandler(Exception)
    def unhandled_error(error):
        app.logger.exception("Unhandled API error: %s", error)
        return jsonify({"error": {"code": "internal_error", "message": "An unexpected server error occurred."}}), 500

    return app


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
