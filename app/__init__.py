import logging
import os

from apiflask import APIFlask
from dotenv import load_dotenv
from flask import render_template, request
from flask_htmx import HTMX
from flask_talisman import Talisman

from .models import db
from .startup_validation import validate_required_env_vars
from .utils import normalize_site_url

logger = logging.getLogger(__name__)


load_dotenv()

htmx = None
STATIC_ASSET_MAX_AGE_SECONDS = 60 * 60 * 24
HTML_PAGE_MAX_AGE_SECONDS = 60 * 60
# Short positive TTL for HTML errors: long enough to absorb bot/miss stampedes,
# short enough that a deploy-time asset 404 cannot pin a .js URL for an hour.
HTML_ERROR_MAX_AGE_SECONDS = 60
HSTS_MAX_AGE_SECONDS = 60 * 60 * 24 * 365
HSTS_HEADER = f"max-age={HSTS_MAX_AGE_SECONDS}; includeSubDomains; preload"


class VersionedStaticAPIFlask(APIFlask):
    def send_static_file(self, filename):
        from .static_assets import (
            DEFAULT_ASSET_VERSION,
            resolve_on_disk_static_filename,
            validate_asset_version,
        )

        version = validate_asset_version(
            self.config.get("ASSET_VERSION", DEFAULT_ASSET_VERSION)
        )
        return super().send_static_file(
            resolve_on_disk_static_filename(filename, version)
        )


def register_template_filters(app):
    import app.filters as filters

    from . import filter_helpers
    from .search import criteria_url_for
    from .static_assets import static_url

    for name in filters.__all__:
        app.add_template_filter(getattr(filters, name))

    for name in filter_helpers.TEMPLATE_FILTERS:
        app.add_template_filter(getattr(filter_helpers, name))

    app.add_template_global(criteria_url_for, "criteria_url_for")
    app.add_template_global(static_url, "static_url")


def create_app(config_name: str = "local") -> APIFlask:
    env_values = validate_required_env_vars()
    app = VersionedStaticAPIFlask(
        __name__, static_url_path="", static_folder="static", docs_path=None
    )

    app.config["CONFIG_NAME"] = config_name
    app.config["INFO"] = {
        "title": "Datagov Catalog",
        "version": "0.1.0",
    }
    if os.getenv("SITE_URL"):
        app.config["SERVERS"] = [{"url": f"{os.getenv('SITE_URL')}"}]

    from .static_assets import get_asset_version

    app.config["PREFERRED_URL_SCHEME"] = "https"
    app.config["ASSET_VERSION"] = get_asset_version()
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = STATIC_ASSET_MAX_AGE_SECONDS

    # enable template hot template reloading in local
    is_local = config_name == "local" or app.config.get("FLASK_ENV") == "local"
    app.config["IS_LOCAL"] = is_local
    if is_local:
        # Enable template auto-reload
        app.config["TEMPLATES_AUTO_RELOAD"] = True
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
        app.config["PREFERRED_URL_SCHEME"] = "http"

    app.config["SECRET_KEY"] = env_values["FLASK_SECRET_KEY"]
    app.config["SQLALCHEMY_DATABASE_URI"] = env_values["DATABASE_URI"]
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

    @app.after_request
    def set_html_cache_control(response):
        if is_local:
            return response

        content_type = response.content_type or ""
        if not content_type.startswith("text/html"):
            return response

        # Keep HTML errors briefly cacheable (not no-store/0): protects origin
        # from miss stampedes, but a deploy-time asset 404 must not stick at a
        # .js/.css URL for the full HTML page TTL.
        if response.status_code >= 400:
            response.cache_control.public = True
            response.cache_control.max_age = HTML_ERROR_MAX_AGE_SECONDS
            response.cache_control.must_revalidate = True
            return response

        if response.cache_control.max_age is not None:
            return response

        response.cache_control.public = True
        response.cache_control.max_age = HTML_PAGE_MAX_AGE_SECONDS
        response.cache_control.must_revalidate = True
        return response

    @app.errorhandler(404)
    def not_found(error):
        if request.blueprint == "api" or request.path.startswith("/api/"):
            return {"message": "Not Found", "detail": {}}, 404
        return render_template("404.html"), 404

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
                "https://*.google-analytics.com",
                "https://*.googletagmanager.com",
            ]
        ),
        "connect-src": " ".join(
            [
                "'self'",
                "https://api.github.com",
                "https://*.google-analytics.com",
                "https://*.analytics.google.com",
                "https://*.googletagmanager.com",
                "https://static.zdassets.com",  # zendesk
                "https://ekr.zdassets.com",  # zendesk
                "https://gsa-solutionshelp.zendesk.com",  # zendesk
                "https://gov-bam.nr-data.net",  # new relic browser monitoring
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
        strict_transport_security_max_age=HSTS_MAX_AGE_SECONDS,
        strict_transport_security_preload=True,
        # our https connections are terminated outside this app
        force_https=False,
    )

    @app.template_global()
    def newrelic_browser_timing_header():
        try:
            import newrelic.agent
        except ImportError:
            return ""

        nonce = getattr(request, "csp_nonce", None)
        return newrelic.agent.get_browser_timing_header(nonce)

    return app


__all__ = ["create_app", "db"]
