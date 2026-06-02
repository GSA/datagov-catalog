"""Helpers for building catalog search filter UI data."""

from __future__ import annotations

# Matches interface.DatabaseInterface.get_top_publishers() (OpenSearch size=100).
TOP_PUBLISHER_COMBO_SIZE = 100


def publisher_names_from_top_publishers(top_publishers: list[dict]) -> list[str]:
    """Publisher names for the combo <select>, sorted alphabetically."""
    return sorted(
        (p["name"] for p in top_publishers if p.get("name")),
        key=lambda name: name.lower(),
    )


def publisher_combo_select_names(
    top_publishers: list[dict],
    suggested: list[str] | None,
    selected: str | None,
) -> list[str]:
    """Deduped publisher <option> values: top publishers, then suggested/current extras."""
    names: list[str] = []
    seen: set[str] = set()

    def add(name: str | None) -> None:
        if not name or name in seen:
            return
        seen.add(name)
        names.append(name)

    for name in publisher_names_from_top_publishers(top_publishers):
        add(name)
    for name in suggested or []:
        add(name)
    add(selected)
    return names
