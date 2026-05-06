import logging
import os

from apiflask import APIFlask
from dotenv import load_dotenv
from flask_htmx import HTMX
from flask_talisman import Talisman

from .models import db
from .utils import normalize_site_url

logger = logging.getLogger(__name__)


load_dotenv()

htmx = None


def register_template_filters(app):
    import app.filters as filters

    for name in filters.__all__:
        app.add_template_filter(getattr(filters, name))


def create_app(config_name: str = "local") -> APIFlask:
    app = APIFlask(__name__, static_url_path="", static_folder="static", docs_path=None)

    app.config["INFO"] = {
        "title": "Datagov Catalog",
        "version": "0.1.0",
    }
    if os.getenv("SITE_URL"):
        app.config["SERVERS"] = [{"url": f"{os.getenv('SITE_URL')}"}]

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

    global htmx
    htmx = HTMX(app)

    db.init_app(app)

    from .routes import register_routes

    register_routes(app)

    from .commands import register_commands

    register_commands(app)

    register_template_filters(app)

    # Content-Security-Policy headers
    # single quotes need to appear in some of the strings
    csp = {
        "default-src": "'self'",
        "script-src": " ".join(
            [
                "'self'",
                "https://*.googletagmanager.com",
                "https://buttons.github.io",  # github button
                "https://unpkg.com",  # swagger
                "'unsafe-hashes'",
                "'sha256-osjxnKEPL/pQJbFk1dKsF7PYFmTyMWGmVSiL9inhxJY='",  # form autosubmit
                "'sha256-A1KDZ6CTgI16YJ4cUNyyCFExM5+Sv4ApvahuZIQRXPA='",  # return to top
                "https://static.zdassets.com",  # zendesk
                "https://ekr.zdassets.com",  # zendesk
                "'sha256-Ff1SFMp5PHyy62W49sHzg1RI9yL6Y9xoqXeGrJP8TUI='",
                "https://gsa-solutionshelp.zendesk.com",  # zendesk
                "'nonce-RgDplMTo1jIsP_9Vr4lErzJtec9zO4Z3'",
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
                "https://raw.githubusercontent.com",  # github logos repo
                "data:",  # leaflet
                "https://cg-1b082c1b-3db7-477f-9ca5-bd51a786b41e.s3-us-gov-west-1.amazonaws.com",  # touchpoints
                "https://touchpoints.app.cloud.gov",  # touchpoints
                "https://*.google-analytics.com",
                "https://*.googletagmanager.com",
            ]
        ),
        "connect-src": " ".join(
            [
                "'self'",
                "https://api.github.com",
                "https://touchpoints.app.cloud.gov",
                "https://*.google-analytics.com",
                "https://*.analytics.google.com",
                "https://*.googletagmanager.com",
                "https://static.zdassets.com",  # zendesk
                "https://ekr.zdassets.com",  # zendesk
                "https://gsa-solutionshelp.zendesk.com",  # zendesk
                "https://*.ingest.de.sentry.io",  # sentry
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
                "https://unpkg.com",  # swagger
                "'unsafe-inline'",  # required for zendesk widget (injects dynamic inline styles)
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
