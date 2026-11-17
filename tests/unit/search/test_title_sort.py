from unittest.mock import patch

import pytest

from app.api_schemas import SearchQuery, SearchResults
from app.routes import _validate_and_normalize_sort
from app.search.config import INDEX_NAME
from app.search.queries import build_sort_clause
from app.search.queries.registry import (
    TITLE_SORT_KEY_SCRIPT,
    TITLE_SORT_MISSING_LAST_SCRIPT,
)


@pytest.mark.parametrize("sort_by", ["title", "TITLE", "Title"])
def test_build_sort_clause_title(sort_by):
    assert build_sort_clause(sort_by) == [
        {
            "_script": {
                "type": "number",
                "order": "asc",
                "script": {
                    "lang": "painless",
                    "source": TITLE_SORT_MISSING_LAST_SCRIPT,
                },
            }
        },
        {
            "_script": {
                "type": "string",
                "order": "asc",
                "script": {"lang": "painless", "source": TITLE_SORT_KEY_SCRIPT},
            }
        },
        {"_id": {"order": "desc"}},
    ]


def test_title_sort_orders_case_insensitively_with_missing_last(interface):
    client = interface.opensearch.client
    titles = {"1": "banana", "2": "Apple", "3": "cherry", "4": None, "5": "apple"}
    for doc_id, title in titles.items():
        body = {"slug": f"title-{doc_id}"}
        if title is not None:
            body["title"] = title
        client.index(index=INDEX_NAME, id=doc_id, body=body)
    client.indices.refresh(index=INDEX_NAME)

    hits = client.search(
        index=INDEX_NAME,
        body={"query": {"match_all": {}}, "sort": build_sort_clause("title")},
    )["hits"]["hits"]

    assert [hit["_id"] for hit in hits] == ["5", "2", "1", "3", "4"]


def test_validate_sort_accepts_title():
    assert _validate_and_normalize_sort("Title", None) == "title"


def test_title_sort_in_api_schemas():
    assert SearchQuery().load({"sort": "title"})["sort"].value == "title"
    assert "title" in SearchResults().fields["sort"].enum.__members__


def test_openapi_sort_enum_includes_title(db_client):
    spec = db_client.get("/openapi.json").get_json()
    sort_schema = spec["components"]["schemas"]["SearchResults"]["properties"]["sort"]
    assert "title" in sort_schema["enum"]


def test_search_api_title_sort_keeps_query_and_filters_across_pages(
    interface, db_client
):
    client = interface.opensearch.client
    titles = ["beta", "ALPHA", "alpha", "Gamma", None]
    for number, title in enumerate(titles, 1):
        body = {
            "slug": f"title-{number:02}",
            "description": "catalogsort",
            "keyword": ["included"],
        }
        if title is not None:
            body["title"] = title
        client.index(index=INDEX_NAME, id=f"{number:02}", body=body)
    excluded = {
        "query-excluded": {"description": "unrelated", "keyword": ["included"]},
        "filter-excluded": {"description": "catalogsort", "keyword": ["other"]},
    }
    for doc_id, body in excluded.items():
        client.index(index=INDEX_NAME, id=doc_id, body={"title": "Aardvark", **body})
    client.indices.refresh(index=INDEX_NAME)

    params = [
        ("q", "catalogsort"),
        ("keyword", "included"),
        ("sort", "title"),
        ("per_page", "2"),
    ]
    slugs, after = [], None
    with patch("app.routes.interface", interface):
        for _ in range(3):
            page_params = params + ([("after", after)] if after else [])
            response = db_client.get("/search", query_string=page_params)
            assert response.status_code == 200
            data = response.get_json()
            assert data["sort"] == "title"
            slugs += [row["slug"] for row in data["results"]]
            after = data.get("after")

    assert slugs == ["title-03", "title-02", "title-01", "title-04", "title-05"]
