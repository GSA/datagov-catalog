"""Helpers for versioned static asset URLs."""

from __future__ import annotations

import os
from urllib.parse import urlencode

from flask import current_app, url_for

DEFAULT_ASSET_VERSION = "dev"


def get_asset_version() -> str:
    """Return the cache-bust version for static assets."""
    env_version = os.getenv("ASSET_VERSION", "").strip()
    return env_version or DEFAULT_ASSET_VERSION


def static_url(filename: str) -> str:
    """Return a static asset URL with a cache-bust query parameter."""
    version = current_app.config.get("ASSET_VERSION", DEFAULT_ASSET_VERSION)
    base_url = url_for("static", filename=filename)
    return f"{base_url}?{urlencode({'v': version})}"
