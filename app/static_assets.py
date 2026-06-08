"""Helpers for versioned static asset URLs."""

import os

from flask import current_app, url_for

DEFAULT_ASSET_VERSION = "dev"


def get_asset_version() -> str:
    """Return the cache-bust version for static assets."""
    env_version = os.getenv("ASSET_VERSION", "").strip()
    return env_version or DEFAULT_ASSET_VERSION


def versioned_static_filename(filename: str, version: str) -> str:
    """Embed the static asset version before the file extension."""
    path, extension = os.path.splitext(filename)
    if extension:
        return f"{path}.{version}{extension}"
    return f"{filename}.{version}"


def unversion_static_filename(filename: str, version: str) -> str:
    """Return the on-disk filename for a versioned static asset request."""
    path, extension = os.path.splitext(filename)
    version_suffix = f".{version}"

    if extension and path.endswith(version_suffix):
        return f"{path[: -len(version_suffix)]}{extension}"
    if not extension and filename.endswith(version_suffix):
        return filename[: -len(version_suffix)]
    return filename


def static_url(filename: str) -> str:
    """Return a static asset URL with the cache-bust version in the filename."""
    version = current_app.config.get("ASSET_VERSION", DEFAULT_ASSET_VERSION)
    return url_for("static", filename=versioned_static_filename(filename, version))
