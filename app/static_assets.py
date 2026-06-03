"""Helpers for versioned static asset URLs."""

from __future__ import annotations

import os
import subprocess
from urllib.parse import urlencode

from flask import current_app, url_for

DEFAULT_ASSET_VERSION = "dev"


def get_asset_version() -> str:
    """Return the cache-bust version for static assets."""
    env_version = os.getenv("ASSET_VERSION", "").strip()
    if env_version:
        return env_version

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        version = result.stdout.strip()
        if version:
            return version
    except (OSError, subprocess.SubprocessError):
        pass

    return DEFAULT_ASSET_VERSION


def static_url(filename: str) -> str:
    """Return a static asset URL with a cache-bust query parameter."""
    version = current_app.config.get("ASSET_VERSION", DEFAULT_ASSET_VERSION)
    base_url = url_for("static", filename=filename)
    return f"{base_url}?{urlencode({'v': version})}"
