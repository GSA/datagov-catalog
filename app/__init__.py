import logging
import os

from dotenv import load_dotenv
from flask import Flask

from .models import db

logger = logging.getLogger(__name__)


load_dotenv()


def create_app():
    app = Flask(__name__, static_url_path="", static_folder="static")

    database_uri = app.config.get("DATABASE_URI") or os.getenv("DATABASE_URI")
    if not database_uri:
        raise RuntimeError(
            "DATABASE_URI must be set in Flask config to connect to harvest database"
        )

    app.config.setdefault("DATABASE_URI", database_uri)
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", database_uri)
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    db.init_app(app)

    from .routes import register_routes

    register_routes(app)

    return app


__all__ = ["create_app", "db"]
