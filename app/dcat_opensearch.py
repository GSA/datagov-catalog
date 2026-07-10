"""DCAT-US 3.0 helpers for OpenSearch indexing and consumer parsing."""

from __future__ import annotations

from typing import Any

_IDENTIFIER_OBJECT_KEYS = ("@id", "notation", "schemaAgency", "version")
_THEME_OBJECT_KEYS = ("@id", "prefLabel", "altLabel", "definition", "notation")


def identifier_id(value: Any) -> str | None:
    """Read the canonical identifier string from a string or Identifier object."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, dict):
        ident = value.get("@id")
        if isinstance(ident, str):
            stripped = ident.strip()
            return stripped or None
    return None


def normalize_identifier(dcat: dict) -> dict | None:
    """Map DCAT-US 1.1 string or 3.0 Identifier object to indexed shape."""
    raw = dcat.get("identifier")
    if raw is None:
        return None

    if isinstance(raw, str):
        stripped = raw.strip()
        return {"@id": stripped} if stripped else None

    if isinstance(raw, dict):
        result = {
            key: raw[key]
            for key in _IDENTIFIER_OBJECT_KEYS
            if isinstance(raw.get(key), str) and raw[key].strip()
        }
        return result or None

    return None


def _normalize_theme_item(theme: Any) -> dict | None:
    if isinstance(theme, str):
        stripped = theme.strip()
        return {"prefLabel": stripped} if stripped else None

    if isinstance(theme, dict):
        result = {
            key: theme[key]
            for key in _THEME_OBJECT_KEYS
            if isinstance(theme.get(key), str) and theme[key].strip()
        }
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

    if isinstance(raw, list):
        themes: list[dict] = []
        for theme in raw:
            item = _normalize_theme_item(theme)
            if item:
                themes.append(item)
        return themes

    return []


def theme_pref_labels(dcat_or_list: dict | list | None) -> list[str]:
    """Extract theme prefLabel strings for geospatial detection and display."""
    if dcat_or_list is None:
        return []

    if isinstance(dcat_or_list, dict):
        return theme_pref_labels(dcat_or_list.get("theme"))

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


def _first_in_series_identifier(dcat: dict) -> str | None:
    raw = dcat.get("inSeries")
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return None

    for series in raw:
        if not isinstance(series, dict):
            continue
        identifier = series.get("@id")
        if isinstance(identifier, str) and identifier.strip():
            return identifier.strip()
    return None


def collection_uri_from_dcat(dcat: dict) -> str | None:
    """Resolve collection/series URI from inSeries or legacy isPartOf."""
    in_series_identifier = _first_in_series_identifier(dcat)
    if in_series_identifier is not None:
        return in_series_identifier

    is_part_of = dcat.get("isPartOf")
    if isinstance(is_part_of, str) and is_part_of.strip():
        return is_part_of.strip()

    return None


def collection_uri_from_hit(doc: dict) -> str | None:
    """Resolve collection URL from an OpenSearch hit."""
    dcat = doc.get("dcat")
    if isinstance(dcat, dict):
        return collection_uri_from_dcat(dcat)

    return None
