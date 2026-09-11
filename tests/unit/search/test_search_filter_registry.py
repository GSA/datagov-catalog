from app.search.queries import (
    MAIN_CONTEXT,
    SearchCriteria,
    build_filter_clauses,
    build_filter_sections,
    build_parents_with_children_query,
    visible_filter_query_params,
)


def test_has_download_filter_parses_and_builds_clause():
    criteria = SearchCriteria.from_request_args(
        {"has_download": "true"}, route_context=MAIN_CONTEXT
    )

    assert criteria.get_filter("has_download") is True
    assert {"term": {"has_download": True}} in build_filter_clauses(criteria)


def test_has_download_filter_defaults_to_inactive():
    criteria = SearchCriteria.from_request_args({}, route_context=MAIN_CONTEXT)

    assert criteria.get_filter("has_download") is None
    assert build_filter_clauses(criteria) == []


def test_has_download_section_is_built_when_active():
    criteria = SearchCriteria.from_values(filters={"has_download": True})

    sections = build_filter_sections(criteria, route_context=MAIN_CONTEXT)
    by_name = {section["name"]: section for section in sections}

    assert by_name["has_download"]["field_name"] == "has_download"
    assert by_name["has_download"]["values"] == ["true"]
    assert by_name["has_download"]["active_summary"] is not None


def test_has_download_is_a_visible_main_context_query_param():
    assert "has_download" in visible_filter_query_params(MAIN_CONTEXT)


def test_collection_filter_builds_top_level_parent_identifier_term():
    criteria = SearchCriteria.from_values(filters={"collection": "parent-1"})

    assert {"term": {"parent_identifier": "parent-1"}} in build_filter_clauses(criteria)


def test_build_parents_with_children_query_filters_and_aggregates_on_parent_identifier():
    query = build_parents_with_children_query(["parent-1", "parent-2"])

    assert query["size"] == 0
    assert query["query"] == {
        "bool": {"filter": [{"terms": {"parent_identifier": ["parent-1", "parent-2"]}}]}
    }
    assert query["aggs"]["parents"]["terms"] == {
        "field": "parent_identifier",
        "size": 2,
    }
