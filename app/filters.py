"""Jinja template filters for the catalog application."""

from datetime import date, datetime
import json
from typing import Any

from flask import url_for


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


__all__ = ["usa_icon", "format_dcat_value"]
