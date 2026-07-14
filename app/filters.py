"""Jinja template filters for the catalog application."""

import html
import json
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any, Union

from bs4 import BeautifulSoup

from app.dcat_normalizer import (
    normalize_access_rights,
    normalize_accrual_periodicity,
    normalize_distribution_license,
    normalize_issued,
    normalize_modified,
    normalize_publisher_sub_org,
)
from app.static_assets import static_url
from shared.constants import ORGANIZATION_TYPE_VALUES


def usa_icon(icon_name: str) -> str:
    """Return SVG markup for a USWDS icon referenced from the sprite sheet."""

    sprite_path = static_url("assets/uswds/img/sprite.svg")
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


_VENDOR_MIME_ALIASES = (
    ("spreadsheetml", "xlsx"),
    ("wordprocessingml", "docx"),
    ("presentationml", "pptx"),
    ("opendocument.spreadsheet", "ods"),
    ("opendocument.text", "odt"),
    ("opendocument.presentation", "odp"),
    ("ms-excel", "xls"),
    ("ms-word", "doc"),
    ("ms-powerpoint", "ppt"),
    ("google-earth.kmz", "kmz"),
    ("google-earth.kml", "kml"),
    ("ogc.wmts", "wmts"),
    ("ogc.wms", "wms"),
    ("ogc.wfs", "wfs"),
    ("ogc.gml", "gml"),
    ("shapefile", "shp"),
)


def _normalize_format(value: str) -> str:
    value = value.lower() if value else "default"
    if "/" in value:
        value = value.split("/")[-1]
    # Strip MIME suffix like "+xml" / "+json" before matching aliases so
    # "vnd.google-earth.kml+xml" matches "google-earth.kml".
    head = value.split("+", 1)[0]
    if head.startswith("vnd."):
        for needle, alias in _VENDOR_MIME_ALIASES:
            if needle in head:
                return alias
    return value


_FORMAT_ICON_MAP = {
    "csv": "csv",
    "json": "json",
    "xml": "xml",
    "rdf+xml": "rdf",
    "rdf": "rdf",
    "pdf": "pdf",
    "html": "html",
    "xhtml+xml": "html",
    "api": "api",
    "zip": "zip",
    "gz": "zip",
    "tar": "zip",
    "7z": "zip",
    "rar": "zip",
    "doc": "word",
    "docx": "word",
    "rtf": "word",
    "odt": "word",
    "xls": "excel",
    "xlsx": "excel",
    "ods": "excel",
    "txt": "text",
    "plain": "text",
    "geo+json": "geojson",
    "geojson": "geojson",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "gif": "image",
    "tiff": "image",
    "webp": "image",
    "svg+xml": "image",
    "svg": "image",
}


def format_icon_class(extension: str) -> str:
    """Return a CSS modifier class for the resource icon based on format."""
    icon = _FORMAT_ICON_MAP.get(_normalize_format(extension), "default")
    return f"file-icon--{icon}"


_OVERLAY_BADGE_MAX_LEN = 4

# Short badge labels for normalized formats that are too long for the icon overlay.
_OVERLAY_BADGE_ALIASES = {
    "octet-stream": "BIN",
    "arcgis geoservices rest api": "REST",
}


def _shorten_overlay_label(label: str) -> str:
    if len(label) <= _OVERLAY_BADGE_MAX_LEN:
        return label

    return label[:_OVERLAY_BADGE_MAX_LEN]


def _extract_badge_source(normalized: str) -> str:
    source = normalized
    if source.startswith("vnd."):
        source = source[4:]
    if source.startswith("x-"):
        source = source[2:]

    if "." in source:
        source = source.rsplit(".", 1)[-1]

    source = source.split("+", 1)[0]
    source = source.split("-", 1)[0]
    source = source.split()[0] if source.split() else source

    return re.sub(r"[^a-z0-9]", "", source.lower())


def _badge_label_from_normalized(normalized: str) -> str:
    if normalized in _OVERLAY_BADGE_ALIASES:
        return _OVERLAY_BADGE_ALIASES[normalized]

    source = _extract_badge_source(normalized)
    if not source:
        return "FILE"

    return _shorten_overlay_label(source.upper())


def format_overlay_label(extension: str) -> str:
    """Short badge text overlaid on the default file icon for formats we don't
    have a dedicated icon for (e.g. KML, WMS, WFS, GML). Returns "" when a
    dedicated icon is available."""
    if not isinstance(extension, str):
        return ""

    normalized = _normalize_format(extension)
    if normalized in _FORMAT_ICON_MAP:
        return ""
    if normalized in ("default", "file", ""):
        return ""
    return _badge_label_from_normalized(normalized)


def format_icon_label(extension: str) -> str:
    """Return a short extension label for inline file icons, or "" for static SVG icons."""
    if not isinstance(extension, str):
        return ""

    normalized = _normalize_format(extension)
    icon = _FORMAT_ICON_MAP.get(normalized, "default")
    if icon == "html":
        return "HTML"
    if icon != "default":
        return ""
    return format_overlay_label(extension)


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


def simplify_resource_type(text: str) -> Union[str, None]:
    """
    returns the basic form of the resource type
    e.g. application/json -> json
    """
    # short circuit for instances where the input is not a str or bytes-like
    if not isinstance(text, str):
        return None

    pattern = "html|json|xml|kml|csv|xls|zip|api|pdf|rdf|nquad|ntriples|turtle"

    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match is not None:
        return match.group(0)


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


def parse_datetime(date_str: str) -> datetime | date | None:
    """
    Parse a date/datetime string into a datetime or date object.
    """
    if not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    if not date_str:
        return None
    if "T" in date_str:
        normalized = date_str.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    try:
        return date.fromisoformat(date_str[:10])
    except ValueError:
        return None


def format_dcat_date(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%B %d, %Y at %I:%M %p")
    if isinstance(value, date):
        return value.strftime("%B %d, %Y")
    return None


def jsonld_distributions(dcatus: dict):
    """
    processes schema.org json-ld distributions. schema.org distributions
    only supports type 'DataDownload' so accessURL is skipped.
    """
    output = []

    distributions = dcatus.get("distribution", [])

    if not distributions:
        return output

    for dist in distributions:
        if dist.get("downloadURL"):
            output.append(
                {
                    "@type": "DataDownload",
                    "encodingFormat": dist.get(
                        "mediaType"
                    ),  # required when downloadURL is present
                    "contentUrl": dist.get("downloadURL"),
                }
            )

    return output


def dcatus_to_schema_org_jsonld(dcatus: dict):
    """
    converts dcatus into schema.org jsonld for google search compatibility

    all inputs are valid dcatus
    """

    return {
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": dcatus.get("title"),  # required
        "description": dcatus.get("description"),  # required
        "url": dcatus.get("landingPage", None),
        "identifier": dcatus.get("identifier"),  # required
        "keywords": dcatus.get("keyword"),  # required
        "license": dcatus.get("license", None),
        "datePublished": dcatus.get("issued", None),
        "dateModified": dcatus.get("modified"),  # required
        "publisher": {
            "@type": "Organization",
            "name": dcatus.get("publisher").get("name"),  # required
        },
        "distribution": jsonld_distributions(dcatus),
    }


def normalize_publisher_name(publisher: Any) -> str:
    """Extract publisher name, normalizing DCAT 3.0 nested subOrganizationOf."""
    if not publisher:
        return ""

    if isinstance(publisher, str):
        return publisher

    if isinstance(publisher, dict):
        normalized = normalize_publisher_sub_org(publisher)
        return normalized.get("name", "")

    return ""


def normalize_license(dcat: dict) -> str | None:
    """Get license, promoting from first distribution if needed (DCAT 3.0)."""
    if not isinstance(dcat, dict):
        return None

    normalized = normalize_distribution_license(dcat)
    return normalized.get("license")


def normalize_access_level(dcat: dict) -> str | None:
    """Get accessLevel, normalizing from accessRights if needed (DCAT 3.0)."""
    if not isinstance(dcat, dict):
        return None

    return normalize_access_rights(dcat.get("accessRights"), dcat.get("accessLevel"))


__all__ = [
    "usa_icon",
    "format_dcat_value",
    "format_gov_type",
    "is_bbox_string",
    "is_geometry_mapping",
    "geometry_to_mapping",
    "format_icon_class",
    "format_icon_label",
    "format_overlay_label",
    "format_contact_point_email",
    "remove_html_tags",
    "simplify_resource_type",
    "json_to_semantic_html",
    "is_json",
    "parse_datetime",
    "format_dcat_date",
    "dcatus_to_schema_org_jsonld",
    "normalize_publisher_name",
    "normalize_license",
    "normalize_access_level",
]
