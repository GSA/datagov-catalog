"""DCAT-US 3.0 helpers for OpenSearch indexing and consumer parsing."""

from __future__ import annotations

from typing import Any

_IDENTIFIER_OBJECT_KEYS = ("@id", "notation", "schemaAgency", "version")
_THEME_OBJECT_KEYS = ("@id", "prefLabel", "altLabel", "definition", "notation")
_IN_SERIES_OBJECT_KEYS = ("@id", "title", "description")


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


def _normalize_in_series_item(series: Any) -> dict | None:
    if isinstance(series, str):
        stripped = series.strip()
        return {"@id": stripped} if stripped else None

    if isinstance(series, dict):
        result = {
            key: series[key]
            for key in _IN_SERIES_OBJECT_KEYS
            if isinstance(series.get(key), str) and series[key].strip()
        }
        return result or None

    return None


def normalize_in_series(dcat: dict) -> list[dict]:
    """Map inSeries objects or legacy isPartOf string to indexed shape."""
    raw = dcat.get("inSeries")
    if raw is not None:
        if isinstance(raw, list):
            series_list: list[dict] = []
            for item in raw:
                normalized = _normalize_in_series_item(item)
                if normalized:
                    series_list.append(normalized)
            if series_list:
                return series_list
        else:
            normalized = _normalize_in_series_item(raw)
            if normalized:
                return [normalized]

    is_part_of = dcat.get("isPartOf")
    if isinstance(is_part_of, str) and is_part_of.strip():
        return [{"@id": is_part_of.strip()}]

    return []


def collection_uri_from_dcat(dcat: dict) -> str | None:
    """Resolve collection/series URI from inSeries or legacy isPartOf."""
    in_series = normalize_in_series(dcat)
    if in_series:
        return in_series[0].get("@id")

    is_part_of = dcat.get("isPartOf")
    if isinstance(is_part_of, str) and is_part_of.strip():
        return is_part_of.strip()

    return None


def collection_uri_from_hit(doc: dict) -> str | None:
    """Resolve collection URL from an OpenSearch hit."""
    in_series = doc.get("inSeries")
    if isinstance(in_series, list) and in_series:
        first = in_series[0]
        if isinstance(first, dict):
            series_id = first.get("@id")
            if isinstance(series_id, str) and series_id.strip():
                return series_id.strip()

    dcat = doc.get("dcat")
    if isinstance(dcat, dict):
        return collection_uri_from_dcat(dcat)

    return None
