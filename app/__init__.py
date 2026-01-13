import logging
import os

from dotenv import load_dotenv
from flask import Flask
from flask_htmx import HTMX
from flask_talisman import Talisman

from .filters import (
    fa_icon_from_extension,
    format_contact_point_email,
    format_dcat_value,
    format_gov_type,
    geometry_to_mapping,
    is_bbox_string,
    is_geometry_mapping,
    remove_html_tags,
    usa_icon,
)
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

    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URI")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SOCIAL_IMAGE_URL"] = os.getenv(
        "SOCIAL_IMAGE_URL",
        "https://s3-us-gov-west-1.amazonaws.com/cg-0817d6e3-93c4-4de8-8b32-da6919464e61/hero-image-bg.png",
    )

    global htmx
    htmx = HTMX(app)

    db.init_app(app)

    from .routes import register_routes

    register_routes(app)

    from .commands import register_commands

    register_commands(app)

    app.add_template_filter(usa_icon)
    app.add_template_filter(format_dcat_value)
    app.add_template_filter(format_gov_type)
    app.add_template_filter(fa_icon_from_extension)
    app.add_template_filter(format_contact_point_email)
    app.add_template_filter(is_bbox_string)
    app.add_template_filter(is_geometry_mapping)
    app.add_template_filter(geometry_to_mapping)
    app.add_template_filter(remove_html_tags)

    # Content-Security-Policy headers
    # single quotes need to appear in some of the strings
    csp = {
        "default-src": "'self'"
    }
    Talisman(app, content_security_policy=csp)

    return app


__all__ = ["create_app", "db"]
