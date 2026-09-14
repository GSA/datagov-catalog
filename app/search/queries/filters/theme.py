from __future__ import annotations

from app.search.queries.filters.base import (
    API_CONTEXT,
    ApiQueryParam,
    FilterDefinition,
    get_list,
)


def _clause(criteria, values: list[str]) -> list[dict]:
    return [{"term": {"theme.normalized": theme.lower()}} for theme in values]


THEME_FILTER = FilterDefinition(
    name="theme",
    query_params=("theme",),
    parse_contexts=(API_CONTEXT,),
    api_query_params=(ApiQueryParam("theme", repeated=True),),
    parse=lambda args: get_list(args, "theme"),
    to_query_pairs=lambda values: [("theme", value) for value in values],
    clause_builder=_clause,
)
