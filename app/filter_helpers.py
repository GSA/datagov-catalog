"""Helpers for building catalog search filter UI data."""

from __future__ import annotations

TEMPLATE_FILTERS = (
    "selection_summary",
    "organization_active_summary",
    "publisher_active_summary",
    "geography_active_summary",
)


def truncate_summary(text: str | None, max_len: int = 48) -> str | None:
    if not text:
        return None
    text = str(text).strip()
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1].rstrip()}…"


def selection_summary(values: list[str] | None) -> str | None:
    values = values or []
    if not values:
        return None
    if len(values) == 1:
        return truncate_summary(values[0])
    return f"{len(values)} selected"


def organization_active_summary(
    selected_organization,
    org_slug: str | None = None,
) -> str | None:
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


def publisher_active_summary(publisher: str | None) -> str | None:
    return truncate_summary(publisher)


def geography_active_summary(
    spatial_geometry,
    geography_label: str | None = None,
) -> str | None:
    if spatial_geometry is None:
        return None
    if geography_label:
        return truncate_summary(geography_label)
    return "Area selected"
