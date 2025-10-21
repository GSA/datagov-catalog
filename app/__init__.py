import logging
import os

from dotenv import load_dotenv
from flask import Flask
from flask_htmx import HTMX

from .models import db
from .filters import format_dcat_value, usa_icon, format_gov_type

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
    app.add_template_filter(usa_icon)
    app.add_template_filter(format_dcat_value)
    app.add_template_filter(format_gov_type)

    return app


__all__ = ["create_app", "db"]
