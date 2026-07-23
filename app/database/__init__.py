"""Database helpers for the catalog application."""

# CatalogDBInterface sets up its own opensearch reader instance
from datagov_data_access.db.interfaces.catalog import (
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
