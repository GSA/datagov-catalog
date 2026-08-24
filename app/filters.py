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
    normalize_distribution_license,
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


# normalized format -> (icon class, badge label, badge color). label/color
# are None for formats that only need an icon; callers generate a short
# fallback label and use the default color for those.
_FORMAT_INFO = {
    "html": ("html", "HTML", "#2e759e"),
    "xhtml+xml": ("html", "HTML", "#2e759e"),
    "json": ("json", "JSON", "#d63b00"),
    "geo+json": ("geojson", "GEOJSON", "#d63b00"),
    "geojson": ("geojson", "GEOJSON", "#d63b00"),
    "xml": ("xml", "XML", "#d63b00"),
    "rdf+xml": ("rdf", "RDF", "#0b4498"),
    "rdf": ("rdf", "RDF", "#0b4498"),
    "turtle": ("default", "RDF", "#0b4498"),
    "ntriples": ("default", "RDF", "#0b4498"),
    "nquad": ("default", "RDF", "#0b4498"),
    "kml": ("default", "KML", "#8B008B"),
    "kmz": ("default", "KML", "#8B008B"),
    "text": ("text", "TXT", "#1a7ea3"),
    "plain": ("text", "TXT", "#1a7ea3"),
    "txt": ("text", "TXT", "#1a7ea3"),
    "csv": ("csv", "CSV", "#856a00"),
    "xls": ("excel", "XLS", "#207e42"),
    "xlsx": ("excel", "XLSX", "#207e42"),
    "ods": ("excel", "ODS", "#207e42"),
    "doc": ("word", "DOC", "#4a2f66"),
    "docx": ("word", "DOCX", "#4a2f66"),
    "odt": ("word", "ODT", "#4a2f66"),
    "rtf": ("word", None, None),
    "ppt": ("default", "PPT", "#4a2f66"),
    "pptx": ("default", "PPTX", "#4a2f66"),
    "zip": ("zip", "ZIP", "#686868"),
    "gz": ("zip", "ZIP", "#686868"),
    "tar": ("zip", "ZIP", "#686868"),
    "7z": ("zip", "ZIP", "#686868"),
    "rar": ("zip", "ZIP", "#686868"),
    "api": ("api", "API", "#d22d81"),
    "pdf": ("pdf", "PDF", "#e0051e"),
    "shp": ("default", "SHP", "#5c4a1a"),
    "png": ("image", None, None),
    "jpg": ("image", None, None),
    "jpeg": ("image", None, None),
    "gif": ("image", None, None),
    "tiff": ("image", None, None),
    "webp": ("image", None, None),
    "svg": ("image", None, None),
    "svg+xml": ("image", None, None),
}

_BADGE_DEFAULT_COLOR = "#3d4551"


def _lookup_format(normalized: str) -> tuple:
    return _FORMAT_INFO.get(normalized, ("default", None, None))


def format_icon_class(extension: str) -> str:
    """Return a CSS modifier class for the resource icon based on format."""
    icon, _, _ = _lookup_format(_normalize_format(extension))
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


_NO_FORMAT = ("default", "file", "")


def _display_label(normalized: str) -> str:
    if normalized in _NO_FORMAT:
        return "FILE"
    _, label, _ = _lookup_format(normalized)
    return label or _badge_label_from_normalized(normalized)


def format_overlay_label(extension: str) -> str:
    """Short badge text overlaid on the default file icon for formats we don't
    have a dedicated icon for (e.g. KML, WMS, WFS, GML). Returns "" when a
    dedicated icon is available."""
    normalized = _normalize_format(extension)
    icon, _, _ = _lookup_format(normalized)
    if icon != "default" or normalized in _NO_FORMAT:
        return ""
    return _shorten_overlay_label(_display_label(normalized))


def format_icon_label(extension: str) -> str:
    """Return a short extension label for inline file icons, or "" for static SVG icons."""
    normalized = _normalize_format(extension)
    icon, _, _ = _lookup_format(normalized)
    if icon == "html":
        return "HTML"
    if icon != "default":
        return ""
    return format_overlay_label(extension)


def normalized_format_label(value: str) -> str:
    """Canonical uppercase format label, shared by cards and the detail page."""
    if not isinstance(value, str) or not value.strip():
        return "FILE"

    return _display_label(_normalize_format(value))


def _extract_url_extension(url: str) -> Union[str, None]:
    if not isinstance(url, str) or not url:
        return None

    path = url.split("?", 1)[0].split("#", 1)[0]
    if "." not in path:
        return None

    ext = path.rsplit(".", 1)[-1]
    if not ext or not ext.isalnum() or len(ext) > 8:
        return None

    return ext


def resolve_resource_format(resource: Mapping) -> Union[str, None]:
    """Raw format string for a resource: format, then mediaType, then URL extension."""
    if not isinstance(resource, Mapping):
        return None

    fmt = resource.get("format")
    if fmt:
        return fmt

    media_type = resource.get("mediaType")
    if media_type:
        return media_type

    url = resource.get("downloadURL") or resource.get("accessURL")
    return _extract_url_extension(url)


def resource_format_badge(resource: Mapping) -> dict:
    """{format, label, color} for a resource; unrecognized formats get a neutral badge, not HTML."""
    raw = resolve_resource_format(resource)
    normalized = _normalize_format(raw) if raw else "file"

    if normalized in _NO_FORMAT:
        return {"format": "file", "label": "FILE", "color": _BADGE_DEFAULT_COLOR}

    _, _, color = _lookup_format(normalized)
    return {
        "format": normalized,
        "label": _display_label(normalized),
        "color": color or _BADGE_DEFAULT_COLOR,
    }


def first_contact_point(contact_point: Any) -> dict:
    """
    Normalize a DCAT contactPoint value to a single vcard:Contact dict.

    Dataset.contactPoint is a single object, but DataService.contactPoint
    is defined as an array of objects (DCAT-US 3.0), so callers that only
    display one contact need the first entry either way.
    """
    if isinstance(contact_point, Mapping):
        return contact_point
    if isinstance(contact_point, Sequence) and not isinstance(
        contact_point, (str, bytes)
    ):
        for item in contact_point:
            if isinstance(item, Mapping):
                return item
    return {}


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
    if not isinstance(text, str):
        return ""
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
        "identifier": dcatus.get("identifier"),  # recommended
        "keywords": dcatus.get("keyword"),  # recommended
        "license": dcatus.get("license", None),
        "datePublished": dcatus.get("issued", None),
        "dateModified": dcatus.get("modified"),
        "publisher": {
            "@type": "Organization",
            "name": (dcatus.get("publisher") or {}).get("name"),
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
    "normalized_format_label",
    "resolve_resource_format",
    "resource_format_badge",
    "format_contact_point_email",
    "first_contact_point",
    "remove_html_tags",
    "json_to_semantic_html",
    "is_json",
    "parse_datetime",
    "format_dcat_date",
    "dcatus_to_schema_org_jsonld",
    "normalize_publisher_name",
    "normalize_license",
    "normalize_access_level",
]
