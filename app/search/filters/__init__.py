from app.search.filters.base import (
    API_CONTEXT,
    DEFAULT_SEARCH_PER_PAGE,
    MAIN_CONTEXT,
    ORGANIZATION_CONTEXT,
    ApiQueryParam,
    FilterDefinition,
    FilterOption,
    FilterParseError,
)
from app.search.filters.collection import COLLECTION_FILTER
from app.search.filters.geography import GEOGRAPHY_FILTER
from app.search.filters.keyword import KEYWORD_FILTER
from app.search.filters.organization import ORGANIZATION_FILTER
from app.search.filters.organization_type import ORGANIZATION_TYPE_FILTER
from app.search.filters.publisher import PUBLISHER_FILTER
from app.search.filters.spatial_data import SPATIAL_DATA_FILTER

__all__ = [
    "API_CONTEXT",
    "ApiQueryParam",
    "COLLECTION_FILTER",
    "DEFAULT_SEARCH_PER_PAGE",
    "FILTERS",
    "FilterDefinition",
    "FilterOption",
    "FilterParseError",
    "GEOGRAPHY_FILTER",
    "KEYWORD_FILTER",
    "MAIN_CONTEXT",
    "ORGANIZATION_CONTEXT",
    "ORGANIZATION_FILTER",
    "ORGANIZATION_TYPE_FILTER",
    "PUBLISHER_FILTER",
    "SPATIAL_DATA_FILTER",
]

FILTERS = (
    GEOGRAPHY_FILTER,
    KEYWORD_FILTER,
    ORGANIZATION_FILTER,
    ORGANIZATION_TYPE_FILTER,
    PUBLISHER_FILTER,
    SPATIAL_DATA_FILTER,
    COLLECTION_FILTER,
)
