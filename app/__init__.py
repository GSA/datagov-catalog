import logging
import os
from pathlib import Path

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
import newrelic.agent
from .utils import normalize_site_url

logger = logging.getLogger(__name__)


load_dotenv()

htmx = None


def create_app(config_name: str = "local") -> Flask:
    app = Flask(__name__, static_url_path="", static_folder="static")

    app.config["PREFERRED_URL_SCHEME"] = "https"
    # enable template hot template reloading in local
    if config_name == "local" or app.config.get("FLASK_ENV") == "local":
        # Enable template auto-reload
        app.config["TEMPLATES_AUTO_RELOAD"] = True
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
        app.config["PREFERRED_URL_SCHEME"] = "http"

    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URI")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SOCIAL_IMAGE_URL"] = os.getenv(
        "SOCIAL_IMAGE_URL",
        "https://s3-us-gov-west-1.amazonaws.com/cg-0817d6e3-93c4-4de8-8b32-da6919464e61/hero-image-bg.png",
    )
    app.config["SERVER_NAME"] = normalize_site_url(
        os.getenv("SITE_URL", "0.0.0.0:8080")
    )

    # configure new relic
    try:
        config_file = Path(__file__).parents[1] / "config" / "newrelic.ini"
        newrelic.agent.initialize(config_file)
        app = newrelic.agent.wsgi_application()(app)
    except Exception as e:
        logger.warning(f"issue initializing new relic: {repr(e)}")

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
        "default-src": "'self'",
        "script-src": " ".join(
            [
                "'self'",
                "https://www.googletagmanager.com",
                "https://buttons.github.io",  # github button
                "https://touchpoints.app.cloud.gov",
                "'unsafe-hashes'",
                "'sha256-osjxnKEPL/pQJbFk1dKsF7PYFmTyMWGmVSiL9inhxJY='",  # form autosubmit
                "'sha256-A1KDZ6CTgI16YJ4cUNyyCFExM5+Sv4ApvahuZIQRXPA='",  # return to top
            ]
        ),
        "font-src": " ".join(
            [
                "'self'",  # USWDS fonts
                "https://cdnjs.cloudflare.com",  # font awesome
            ]
        ),
        "img-src": " ".join(
            [
                "'self'",
                "https://s3-us-gov-west-1.amazonaws.com",  # logos
                "data:",  # leaflet
                "https://cg-1b082c1b-3db7-477f-9ca5-bd51a786b41e.s3-us-gov-west-1.amazonaws.com",  # touchpoints
                "https://touchpoints.app.cloud.gov",  # touchpoints
            ]
        ),
        "connect-src": " ".join(
            [
                "'self'",
                "https://api.github.com",
                "https://touchpoints.app.cloud.gov",
            ]
        ),
        "frame-src": "https://www.googletagmanager.com",
        "style-src-attr": " ".join(
            [
                "'self'",
                "'unsafe-hashes'",
                "'sha256-kELgoK46JmGjLd8UHfzN0qJToDgIB+yMtRHG8PtGL7s='",  # Google tag manager inline
            ]
        ),
        "style-src": " ".join(
            [
                "'self'",  # local styles.css
                "https://cdnjs.cloudflare.com",  # font-awesome
            ]
        ),
        "style-src-elem": " ".join(
            [
                "'self'",  # local styles.css
                "https://cdnjs.cloudflare.com",  # font-awesome
                "'sha256-faU7yAF8NxuMTNEwVmBz+VcYeIoBQ2EMHW3WaVxCvnk='",  # htms.min.js
                "'sha256-qo7STIM1L/OgU9y0De47mqod1UZFLJfTn36bRC42rfA='",  # buttons.js
                "'sha256-d0LwTCBHt5DXTdSVbRSm0wQ/W4m5yoyMcrge+KrScUc='",  # touchpoints
            ]
        ),
    }
    Talisman(
        app,
        content_security_policy=csp,
        content_security_policy_nonce_in=["script-src"],
        # our https connections are terminated outside this app
        force_https=False,
    )

    return app


__all__ = ["create_app", "db"]
