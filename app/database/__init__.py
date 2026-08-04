"""Database helpers for the catalog application."""

# CatalogDBInterface lazily sets up its own opensearch reader instance
from .interface import (
    DEFAULT_PAGE,
    DEFAULT_PER_PAGE,
    SEARCH_API_MAX_PER_PAGE,
    CatalogDBInterface,
)

__all__ = [
    "CatalogDBInterface",
    DEFAULT_PER_PAGE,
    DEFAULT_PAGE,
    SEARCH_API_MAX_PER_PAGE,
]
