"""Helpers for versioned static asset URLs."""

import os
import re

from flask import current_app, url_for

DEFAULT_ASSET_VERSION = "dev"
# Must stay in sync with .github/scripts/compute-asset-version.sh (sha256 prefix).
DEPLOY_ASSET_VERSION_PATTERN = re.compile(r"^[0-9a-f]{7}$")


def validate_asset_version(version: str) -> str:
    """Return a filename-safe static asset version."""
    if version == DEFAULT_ASSET_VERSION or DEPLOY_ASSET_VERSION_PATTERN.fullmatch(
        version
    ):
        return version
    raise ValueError(
        "ASSET_VERSION must be 'dev' or a 7-character lowercase hex digest"
    )


def get_asset_version() -> str:
    """Return the cache-bust version for static assets."""
    env_version = os.getenv("ASSET_VERSION", "").strip()
    return validate_asset_version(env_version or DEFAULT_ASSET_VERSION)


def versioned_static_filename(filename: str, version: str) -> str:
    """Embed the static asset version before the file extension."""
    path, extension = os.path.splitext(filename)
    if extension:
        return f"{path}.{version}{extension}"
    return f"{filename}.{version}"


def resolve_on_disk_static_filename(
    filename: str, version: str = DEFAULT_ASSET_VERSION
) -> str:
    """Map a versioned static URL path to the on-disk filename.

    Strips a final segment before the extension when it is either the current
    ASSET_VERSION (e.g. local ``dev``) or a 7-character lowercase hex deploy
    hash. That covers the current deploy and prior deploys still referenced by
    cached HTML, without guessing at tokens like ``min``.
    """
    path, extension = os.path.splitext(filename)
    if not extension:
        return filename

    base, separator, maybe_version = path.rpartition(".")
    if not separator or not base:
        return filename

    if maybe_version == version or DEPLOY_ASSET_VERSION_PATTERN.fullmatch(
        maybe_version
    ):
        return f"{base}{extension}"
    return filename


def static_url(filename: str) -> str:
    """Return a static asset URL with the cache-bust version in the filename."""
    version = validate_asset_version(
        current_app.config.get("ASSET_VERSION", DEFAULT_ASSET_VERSION)
    )
    return url_for("static", filename=versioned_static_filename(filename, version))
