"""DCAT helpers for OpenSearch indexing and consumer parsing."""

from __future__ import annotations

from typing import Any

_THEME_OBJECT_KEYS = ("@id", "prefLabel", "altLabel", "definition", "notation")


def _clean_string(value: Any) -> str | None:
    """Return a non-empty, stripped string or None."""
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def identifier_id(value: Any) -> str | None:
    """Read the canonical identifier string from a string or Identifier object."""
    if value is None:
        return None
    if isinstance(value, str):
        return _clean_string(value)
    if isinstance(value, dict):
        return _clean_string(value.get("@id"))
    return None


def _id_from_string_or_object(value: Any) -> str | None:
    """Read a non-empty identifier from a DCAT string or object value."""
    if isinstance(value, str):
        return _clean_string(value)
    if isinstance(value, dict):
        return _clean_string(value.get("@id"))
    return None


def dcat_uri(value: Any) -> str | None:
    """Resolve a DCAT URI from a string value or object with @id."""
    return _id_from_string_or_object(value)


def normalize_text(value: Any) -> str:
    """Return a string for text index fields, or empty string for other shapes."""
    return value if isinstance(value, str) else ""


def normalize_identifier(dcat: dict) -> str | None:
    """Map DCAT-US string or Identifier object to the scalar indexed shape."""
    raw = dcat.get("identifier")
    if raw is None:
        return None

    return _id_from_string_or_object(raw)


def _collection_uri_from_in_series(value: Any) -> str | None:
    """Resolve the first collection URI from a DCAT-US 3.0 inSeries value."""
    if not isinstance(value, list):
        return _id_from_string_or_object(value)

    for series in value:
        uri = _id_from_string_or_object(series)
        if uri:
            return uri
    return None


def _normalize_scalar_or_list(value: Any) -> str | list[str] | None:
    """Keep non-empty string values, including arrays of strings."""
    scalar = _clean_string(value)
    if scalar is not None:
        return scalar

    if isinstance(value, list):
        items = [
            item.strip() for item in value if isinstance(item, str) and item.strip()
        ]
        if items:
            return items

    return None


def _normalize_theme_item(theme: Any) -> dict | None:
    if isinstance(theme, str):
        stripped = theme.strip()
        return {"prefLabel": stripped} if stripped else None

    if isinstance(theme, dict):
        result: dict[str, str | list[str]] = {}
        for key in _THEME_OBJECT_KEYS:
            if key not in theme:
                continue
            value = _normalize_scalar_or_list(theme[key])
            if value is not None:
                result[key] = value
        return result or None

    return None


def normalize_theme(dcat: dict) -> list[dict]:
    """Map DCAT-US 1.1 strings or 3.0 Concept objects to indexed shape."""
    raw = dcat.get("theme")
    if raw is None:
        return []

    if isinstance(raw, str):
        item = _normalize_theme_item(raw)
        return [item] if item else []

    if isinstance(raw, dict):
        item = _normalize_theme_item(raw)
        return [item] if item else []

    if isinstance(raw, list):
        themes: list[dict] = []
        for theme in raw:
            item = _normalize_theme_item(theme)
            if item:
                themes.append(item)
        return themes

    return []


def normalize_keywords(value: Any) -> list[str]:
    """Coerce DCAT keywords into a list of non-empty strings."""
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [item.strip() for item in items if isinstance(item, str) and item.strip()]


def normalize_publisher_name(value: Any) -> str:
    """Extract the publisher display name from name, then prefLabel."""
    if not isinstance(value, dict):
        return ""
    return (
        _clean_string(value.get("name")) or _clean_string(value.get("prefLabel")) or ""
    )


def distribution_titles(value: Any) -> list[str]:
    """Extract non-empty distribution titles from a distribution list."""
    if not isinstance(value, list):
        return []
    titles: list[str] = []
    for dist in value:
        if not isinstance(dist, dict):
            continue
        title = _clean_string(dist.get("title"))
        if title is not None:
            titles.append(title)
    return titles


def theme_pref_labels(dcat_or_list: dict | list | None) -> list[str]:
    """Extract theme prefLabel strings for geospatial detection and display."""
    if dcat_or_list is None:
        return []

    if isinstance(dcat_or_list, dict):
        if "theme" in dcat_or_list:
            return theme_pref_labels(dcat_or_list.get("theme"))
        pref_label = dcat_or_list.get("prefLabel")
        if isinstance(pref_label, str):
            stripped = pref_label.strip()
            return [stripped] if stripped else []
        return []

    if isinstance(dcat_or_list, str):
        stripped = dcat_or_list.strip()
        return [stripped] if stripped else []

    if isinstance(dcat_or_list, list):
        labels: list[str] = []
        for item in dcat_or_list:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    labels.append(stripped)
            elif isinstance(item, dict):
                pref_label = item.get("prefLabel")
                if isinstance(pref_label, str):
                    stripped = pref_label.strip()
                    if stripped:
                        labels.append(stripped)
        return labels

    return []


def collection_uri_from_dcat(dcat: dict) -> str | None:
    """Resolve collection URI from legacy isPartOf or DCAT-US 3.0 inSeries."""
    uri = _id_from_string_or_object(dcat.get("isPartOf"))
    if uri:
        return uri
    return _collection_uri_from_in_series(dcat.get("inSeries"))


def collection_uri_from_hit(doc: dict) -> str | None:
    """Resolve collection URL from an OpenSearch hit."""
    dcat = doc.get("dcat")
    if isinstance(dcat, dict):
        return collection_uri_from_dcat(dcat)

    return None
