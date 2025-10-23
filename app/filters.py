"""Jinja template filters for the catalog application."""

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from flask import url_for

from shared.constants import ORGANIZATION_TYPE_VALUES


def usa_icon(icon_name: str) -> str:
    """Return SVG markup for a USWDS icon referenced from the sprite sheet."""

    sprite_path = url_for("static", filename="assets/uswds/img/sprite.svg")
    return (
        '<svg class="usa-icon" aria-hidden="true" role="img">'
        f'<use xlink:href="{sprite_path}#{icon_name}"></use>'
        "</svg>"
    )


def _json_default(value: Any) -> str:
    """Fallback serializer for objects that JSON does not handle by default."""

    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def format_dcat_value(value: Any) -> str:
    """Return a human-readable string for DCAT metadata values."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, indent=2, sort_keys=True, default=_json_default)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def format_gov_type(gov_type: str) -> str:
    """Format a government type value for display."""
    if gov_type in ORGANIZATION_TYPE_VALUES:
        return gov_type.split()[0].lower()
    return "unknown"


def is_bbox_string(value: Any) -> bool:
    """Return True when value looks like a numeric bbox string."""

    if not isinstance(value, str):
        return False

    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        return False

    try:
        # Ensure all parts convert cleanly to floats.
        [float(part) for part in parts]
    except ValueError:
        return False

    return True


def is_geometry_mapping(value: Any) -> bool:
    """Return True when value looks like a GeoJSON geometry mapping."""

    if not isinstance(value, Mapping):
        return False

    geom_type = value.get("type")
    coords = value.get("coordinates")

    if not isinstance(geom_type, str):
        return False
    if coords is None:
        return False
    if isinstance(coords, (str, bytes)):
        return False
    if not isinstance(coords, Sequence):
        return False

    return True


__all__ = [
    "usa_icon",
    "format_dcat_value",
    "format_gov_type",
    "is_bbox_string",
    "is_geometry_mapping",
]
