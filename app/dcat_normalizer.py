"""
DCAT-US 3.0 to 1.1 Display Normalization

This module provides functions to normalize DCAT-US 3.0 dataset metadata
to DCAT-US 1.1 format for consistent display in the UI.
"""

from typing import Any


def normalize_rights(rights: Any) -> str | None:
    """
    Convert DCAT 3.0 rights (array) back to 1.1 format (string).

    v3.0: ["This data is in the public domain."]
    v1.1: "This data is in the public domain."
    """
    if not rights:
        return None

    if isinstance(rights, str):
        return rights

    if isinstance(rights, list) and len(rights) > 0:
        return rights[0]

    return None
