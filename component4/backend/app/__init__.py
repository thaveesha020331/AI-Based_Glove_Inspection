from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI="sqlite:///gloveiq-dev.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        FRONTEND_ORIGIN="http://localhost:5173",
    )
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}})

    from app.api.health import health_bp
    from app.api.overview import overview_bp
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(overview_bp, url_prefix="/api")
    return app
