from __future__ import annotations

from app.search.queries.filters.base import (
    API_CONTEXT,
    MAIN_CONTEXT,
    ApiQueryParam,
    FilterDefinition,
    parse_string,
)


def _clause(criteria, value: str) -> dict:
    normalized_value = (value or "").strip().lower()
    return {"term": {"access_level": normalized_value}}


def _parse(args):
    # Support both the internal snake_case name and the DCAT-style
    # camelCase alias used by external clients/UI links.
    return parse_string(args, "access_level") or parse_string(args, "accessLevel")


ACCESS_LEVEL_FILTER = FilterDefinition(
    name="access_level",
    query_params=("access_level", "accessLevel"),
    parse_contexts=(MAIN_CONTEXT, API_CONTEXT),
    api_query_params=(ApiQueryParam("accessLevel"),),
    parse=_parse,
    to_query_pairs=lambda value: [("accessLevel", value)],
    clause_builder=_clause,
)
