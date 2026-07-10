import pytest
from werkzeug.datastructures import MultiDict

from app.search import (
    API_CONTEXT,
    FILTERS,
    MAIN_CONTEXT,
    FilterParseError,
    SearchCriteria,
    build_aggregation_specs,
    build_filter_clauses,
    build_filter_sections,
    parse_filter_aggregations,
    visible_filter_query_params,
)


def test_search_criteria_parses_registered_filters():
    criteria = SearchCriteria.from_request_args(
        MultiDict(
            [
                ("q", "water"),
                ("keyword", "health"),
                ("keyword", "education"),
                ("org_type", "City Government"),
                ("publisher", "City Publisher"),
                ("org_slug", "city-example"),
                ("spatial_filter", "geospatial"),
                ("collection", "collection-id"),
                ("sort", "popularity"),
            ]
        ),
        route_context=MAIN_CONTEXT,
    )

    assert criteria.query == "water"
    assert criteria.keywords == ["health", "education"]
    assert criteria.org_types == ["City Government"]
    assert criteria.publisher == "City Publisher"
    assert criteria.org_slug == "city-example"
    assert criteria.spatial_filter == "geospatial"
    assert criteria.collection == "collection-id"
    assert criteria.sort_by == "popularity"


def test_search_criteria_rejects_malformed_spatial_geometry():
    with pytest.raises(FilterParseError) as excinfo:
        SearchCriteria.from_request_args(
            MultiDict([("spatial_geometry", "{bad-json")]),
            route_context=API_CONTEXT,
        )

    assert excinfo.value.parameter == "spatial_geometry"
    assert excinfo.value.message == "spatial_geometry parameter is malformed"


def test_query_params_are_generated_from_registered_filters():
    criteria = SearchCriteria.from_request_args(
        MultiDict(
            [
                ("q", "parks"),
                ("keyword", "trees"),
                ("keyword", "transit"),
                ("spatial_geometry", '{"type":"Point","coordinates":[-75,40]}'),
                ("spatial_within", "false"),
                ("geography_label", "Example Place"),
            ]
        ),
        route_context=MAIN_CONTEXT,
    )

    params = criteria.to_query_dict(include_query=True, include_sort=True)

    assert params["q"] == "parks"
    assert params["sort"] == "relevance"
    assert params["keyword"] == ["trees", "transit"]
    assert params["spatial_within"] == "false"
    assert params["geography_label"] == "Example Place"
    assert params["spatial_geometry"] == '{"type":"Point","coordinates":[-75,40]}'


def test_filter_clauses_are_built_from_registered_filters():
    criteria = SearchCriteria.from_request_args(
        MultiDict(
            [
                ("keyword", "health"),
                ("org_slug", "city-example"),
                ("org_type", "City Government"),
                ("publisher", "City Publisher"),
                ("spatial_filter", "non-geospatial"),
                ("collection", "collection-id"),
            ]
        ),
        route_context=MAIN_CONTEXT,
    )
    criteria.set_resolved_filter("organization", "org-id")

    clauses = build_filter_clauses(criteria)

    assert {"term": {"keyword.normalized": "health"}} in clauses
    assert {"term": {"publisher.normalized": "city publisher"}} in clauses
    assert {"term": {"has_spatial": False}} in clauses
    assert {
        "nested": {
            "path": "organization",
            "query": {"term": {"organization.id": "org-id"}},
        }
    } in clauses
    assert {
        "nested": {
            "path": "organization",
            "query": {"terms": {"organization.organization_type": ["City Government"]}},
        }
    } in clauses
    assert {
        "nested": {
            "path": "dcat",
            "query": {"term": {"dcat.isPartOf": "collection-id"}},
        }
    } in clauses


def test_aggregation_specs_and_parsing_are_registry_owned():
    criteria = SearchCriteria(include_aggregations=True, keyword_size=5)

    specs = build_aggregation_specs(criteria)

    assert set(specs) == {"unique_keywords", "organizations", "unique_publishers"}
    assert specs["unique_keywords"]["terms"]["size"] == 5

    parsed = parse_filter_aggregations(
        {
            "unique_keywords": {"buckets": [{"key": "health", "doc_count": 3}]},
            "organizations": {
                "by_slug": {"buckets": [{"key": "org-slug", "doc_count": 2}]}
            },
            "unique_publishers": {"buckets": [{"key": "Publisher", "doc_count": 1}]},
        }
    )

    assert parsed == {
        "keywords": [{"keyword": "health", "count": 3}],
        "organizations": [{"slug": "org-slug", "count": 2}],
        "publishers": [{"name": "Publisher", "count": 1}],
    }


def test_fixed_option_sections_are_built_by_filter_definitions():
    criteria = SearchCriteria.from_values(
        filters={
            "org_type": ["City Government"],
            "spatial_data": "geospatial",
        }
    )

    sections = build_filter_sections(criteria, route_context=MAIN_CONTEXT)
    by_name = {section["name"]: section for section in sections}

    assert by_name["org_type"]["field_name"] == "org_type"
    assert by_name["org_type"]["values"] == ["City Government"]
    assert by_name["org_type"]["active_summary"] == "City Government"
    assert by_name["spatial_data"]["field_name"] == "spatial_filter"
    assert by_name["spatial_data"]["value"] == "geospatial"
    assert by_name["spatial_data"]["active_summary"] == "Geospatial only"


def test_visible_filter_query_params_come_from_registered_sections():
    assert visible_filter_query_params(MAIN_CONTEXT) >= {
        "keyword",
        "org_slug",
        "org_type",
        "publisher",
        "spatial_filter",
        "spatial_geometry",
        "spatial_within",
        "geography_label",
    }
    assert "collection" not in visible_filter_query_params(MAIN_CONTEXT)


def test_api_filter_schema_metadata_matches_registered_query_params():
    for definition in FILTERS:
        if API_CONTEXT not in definition.parse_contexts:
            continue

        documented_params = {param.name for param in definition.api_query_params}

        assert documented_params == set(definition.query_params), definition.name


def test_from_values_accepts_generic_filter_map():
    criteria = SearchCriteria.from_values(
        query="water",
        filters={
            "keyword": ["health"],
            "collection": "collection-id",
            "geography": {
                "geometry": {"type": "Point", "coordinates": [-75, 40]},
                "within": False,
                "label": "Example",
            },
        },
    )

    assert criteria.query == "water"
    assert criteria.keywords == ["health"]
    assert criteria.collection == "collection-id"
    assert criteria.spatial_geometry == {"type": "Point", "coordinates": [-75, 40]}
    assert criteria.spatial_within is False
