import os

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
    )
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}})

    from app.api.v1 import api_v1_bp
    from app.api.health import health_bp
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")
    app.register_blueprint(health_bp, url_prefix="/api")

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
