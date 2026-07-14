from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import url_for

from app.search.criteria import SearchCriteria
from app.search.filters import FILTERS


def build_filter_clauses(criteria: SearchCriteria) -> list[dict]:
    clauses: list[dict] = []
    for definition in FILTERS:
        if definition.clause_builder is None:
            continue
        value = criteria.get_resolved_filter(definition.name)
        if not definition.is_active(value):
            continue
        clause = definition.clause_builder(criteria, value)
        if clause is None:
            continue
        if isinstance(clause, list):
            clauses.extend(clause)
        else:
            clauses.append(clause)
    return clauses


def build_aggregation_specs(criteria: SearchCriteria) -> dict[str, dict]:
    specs = {}
    for definition in FILTERS:
        if definition.aggregation_name and definition.aggregation_builder:
            aggregation = definition.aggregation_builder(criteria)
            if aggregation is not None:
                specs[definition.aggregation_name] = aggregation
    return specs


def parse_filter_aggregations(raw_aggs: Mapping[str, Any] | None) -> dict | None:
    if raw_aggs is None:
        return None
    parsed = {}
    for definition in FILTERS:
        if definition.aggregation_parser is not None:
            parsed_name = definition.aggregation_result_key or definition.name
            parsed[parsed_name] = definition.aggregation_parser(raw_aggs)
    return parsed


def build_filter_sections(
    criteria: SearchCriteria,
    *,
    route_context: str,
    selected_organization=None,
    suggested_keywords=None,
    suggested_organizations=None,
    suggested_publishers=None,
    contextual_keyword_counts=None,
    contextual_org_counts=None,
    contextual_publisher_counts=None,
    search_result_geometries=None,
) -> list[dict]:
    context = {
        "selected_organization": selected_organization,
        "suggested_keywords": suggested_keywords,
        "suggested_organizations": suggested_organizations,
        "suggested_publishers": suggested_publishers,
        "contextual_keyword_counts": contextual_keyword_counts,
        "contextual_org_counts": contextual_org_counts,
        "contextual_publisher_counts": contextual_publisher_counts,
        "search_result_geometries": search_result_geometries,
    }
    sections = []
    for definition in FILTERS:
        if route_context not in definition.ui_contexts:
            continue
        if definition.section_builder is None:
            continue
        value = criteria.get_filter(definition.name)
        section = {
            "name": definition.name,
            "label": definition.label,
            "renderer": definition.renderer,
            "value": value,
            "is_active": definition.is_active(value),
            "options": definition.options,
        }
        section.update(definition.section_builder(criteria, context))
        sections.append(section)
    return sections


def visible_filter_query_params(route_context: str) -> set[str]:
    params: set[str] = set()
    for definition in FILTERS:
        if route_context in definition.ui_contexts:
            params.update(definition.query_params)
    return params


def criteria_url_for(
    endpoint: str, params: Mapping[str, Any] | None = None, **extra
) -> str:
    values: dict[str, Any] = {}
    for source in (params or {}, extra):
        for key, value in source.items():
            if value is None or value == []:
                continue
            values[key] = value
    return url_for(endpoint, **values)
