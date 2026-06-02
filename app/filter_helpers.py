"""Helpers for building catalog search filter UI data."""

from __future__ import annotations


def truncate_summary(text: str | None, max_len: int = 48) -> str | None:
    if not text:
        return None
    text = str(text).strip()
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1].rstrip()}…"


def keyword_active_summary(keywords: list[str] | None) -> str | None:
    keywords = keywords or []
    if not keywords:
        return None
    if len(keywords) == 1:
        return truncate_summary(keywords[0])
    return f"{len(keywords)} selected"


def organization_active_summary(args) -> str | None:
    if isinstance(args, tuple):
        selected_organization, org_slug = args
    else:
        selected_organization, org_slug = args, None
    if selected_organization is not None:
        name = getattr(selected_organization, "name", None) or (
            selected_organization.get("name")
            if isinstance(selected_organization, dict)
            else None
        )
        return truncate_summary(name)
    if org_slug:
        return truncate_summary(org_slug.replace("-", " ").title())
    return None


def organization_type_active_summary(org_types: list[str] | None) -> str | None:
    org_types = org_types or []
    if not org_types:
        return None
    if len(org_types) == 1:
        return truncate_summary(org_types[0])
    return f"{len(org_types)} selected"


def publisher_active_summary(publisher: str | None) -> str | None:
    return truncate_summary(publisher)


def geography_active_summary(args) -> str | None:
    if isinstance(args, tuple):
        spatial_geometry, geography_label = args
    else:
        spatial_geometry, geography_label = args, None
    if spatial_geometry is None:
        return None
    if geography_label:
        return truncate_summary(geography_label)
    return "Area selected"


def spatial_data_active_summary(spatial_filter: str | None) -> str | None:
    labels = {
        "geospatial": "Geospatial only",
        "non-geospatial": "Non-geospatial only",
    }
    return labels.get(spatial_filter or "")


def has_active_filters(
    *,
    keywords=None,
    org_types=None,
    publisher=None,
    org_slug=None,
    selected_organization=None,
    spatial_filter=None,
    spatial_geometry=None,
) -> bool:
    return bool(
        (keywords and len(keywords) > 0)
        or (org_types and len(org_types) > 0)
        or publisher
        or org_slug
        or selected_organization
        or spatial_filter
        or spatial_geometry is not None
    )
