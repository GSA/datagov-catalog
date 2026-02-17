"""Jinja template filters for the catalog application."""

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any, Union
import html

from bs4 import BeautifulSoup
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


def format_gov_type(gov_type: str, lower=True) -> str:
    """Format a government type value for display."""
    if gov_type in ORGANIZATION_TYPE_VALUES:
        data = gov_type.split()[0]
        if lower:
            return data.lower()
        return data
    return "unknown"


def fa_icon_from_extension(extension: str) -> str:
    """Return a Font Awesome icon class based on file extension."""
    extension = extension.lower() if extension else "default"
    # if extension is a MIME type, extract the last part
    # e.g. "application/json" -> "json"
    if "/" in extension:
        extension = extension.split("/")[-1]
    if extension in ["csv"]:
        return "fa-file-csv"
    elif extension in ["xlsx", "xls", "ods"]:
        return "fa-file-excel"
    elif extension in ["pdf"]:
        return "fa-file-pdf"
    elif extension in ["html"]:
        return "fa-arrow-up-right-from-square"
    elif extension in ["api"]:
        return "fa-plug"
    else:
        return "fa-file"


def format_contact_point_email(email: str) -> Union[str, None]:
    """Format a contact point email for display."""
    if email:
        if ":" in email:
            # If the email is in the format "mailto:email", return only the email part
            return email.split(":")[-1].strip().lower()
        return email.split().lower()
    return None


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

    return geometry_to_mapping(value) is not None


def geometry_to_mapping(value: Any) -> Mapping | None:
    """Return a mapping version of the geometry, parsing JSON strings when needed."""

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None

    if not isinstance(value, Mapping):
        return None

    geom_type = value.get("type")
    coords = value.get("coordinates")

    if not isinstance(geom_type, str):
        return None
    if coords is None:
        return None
    if isinstance(coords, (str, bytes)):
        return None
    if not isinstance(coords, Sequence):
        return None

    return value


def remove_html_tags(text: str) -> str:
    """
    removes html tags from [text]
    """
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text()


def json_to_semantic_html(obj, indent=2, level=0):
    """
    render a Python dict/list as semantic JSON HTML
    with blue keys and green values.
    """
    pad = " " * (indent * level)
    next_pad = " " * (indent * (level + 1))

    if isinstance(obj, dict):
        if not obj:
            return '<span class="punctuation">{}</span>'

        items = []
        for i, (k, v) in enumerate(obj.items()):
            comma = '<span class="punctuation">,</span>' if i < len(obj) - 1 else ""
            items.append(
                f"{next_pad}"
                f'<span class="key">"{html.escape(str(k))}"</span>'
                f'<span class="punctuation">: </span>'
                f"{json_to_semantic_html(v, indent, level + 1)}"
                f"{comma}"
            )

        return (
            '<span class="punctuation">{</span>\n'
            + "\n".join(items)
            + "\n"
            + f'{pad}<span class="punctuation">}}</span>'
        )

    if isinstance(obj, list):
        if not obj:
            return '<span class="punctuation">[]</span>'

        items = []
        for i, v in enumerate(obj):
            comma = '<span class="punctuation">,</span>' if i < len(obj) - 1 else ""
            items.append(
                f"{next_pad}{json_to_semantic_html(v, indent, level + 1)}{comma}"
            )

        return (
            '<span class="punctuation">[</span>\n'
            + "\n".join(items)
            + "\n"
            + f'{pad}<span class="punctuation">]</span>'
        )

    # Scalars
    if isinstance(obj, str):
        return f'<span class="string">"{html.escape(obj)}"</span>'

    if isinstance(obj, bool):
        return f'<span class="boolean">{str(obj).lower()}</span>'

    if obj is None:
        return '<span class="null">null</span>'

    # numbers
    return f'<span class="number">{obj}</span>'


def is_json(value):
    try:
        json.loads(value)
        return True
    except (TypeError, ValueError):
        return False


__all__ = [
    "usa_icon",
    "format_dcat_value",
    "format_gov_type",
    "is_bbox_string",
    "is_geometry_mapping",
    "geometry_to_mapping",
    "fa_icon_from_extension",
    "format_contact_point_email",
    "remove_html_tags",
    "json_to_semantic_html",
    "is_json",
]
