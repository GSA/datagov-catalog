import logging
import os

from dotenv import load_dotenv
from flask import Flask
from flask_htmx import HTMX

from .filters import usa_icon
from .models import db

logger = logging.getLogger(__name__)


load_dotenv()

htmx = None


def create_app(config_name: str = "local") -> Flask:
    app = Flask(__name__, static_url_path="", static_folder="static")
    # enable template hot template reloading in local
    if config_name == "local" or app.config.get("FLASK_ENV") == "local":
        # Enable template auto-reload
        app.config["TEMPLATES_AUTO_RELOAD"] = True
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URI")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    global htmx
    htmx = HTMX(app)

    db.init_app(app)

    from .routes import register_routes

    register_routes(app)

    from .commands import register_commands

    register_commands(app)

    app.add_template_filter(usa_icon)

    return app


__all__ = ["create_app", "db"]
