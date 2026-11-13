from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from bs4 import BeautifulSoup

from app.api_schemas import SearchQuery, SearchResults
from app.models import Organization
from app.search.config import INDEX_NAME
from app.search.queries import build_sort_clause


@pytest.mark.parametrize("sort", ["title", "TITLE"])
def test_title_sort_clause(sort):
    assert build_sort_clause(sort) == [
        {"title.normalized": {"order": "asc", "missing": "_last"}},
        {"_id": {"order": "desc"}},
    ]


def test_title_sort_is_available_in_request_and_response_schemas():
    assert SearchQuery().load({"sort": "title"})["sort"].value == "title"
    assert "title" in SearchResults().fields["sort"].enum.__members__


def test_title_sort_api_preserves_filters_and_paginates_equal_and_missing_titles(
    interface, db_client
):
    client = interface.opensearch.client
    titles = ["alpha", "ALPHA", "alpha", "Beta", "The Zebra", "zebra", None, None]
    for number, title in enumerate(titles, 1):
        document = {
            "slug": f"title-{number}",
            "description": "catalogsort",
            "keyword": ["included", "second"],
        }
        # Cover both an absent title and an explicit null.
        if number != 7:
            document["title"] = title
        client.index(index=INDEX_NAME, id=f"{number:02}", body=document)
    for doc_id, description, keywords in [
        ("query-excluded", "unrelated", ["included", "second"]),
        ("filter-excluded", "catalogsort", ["included"]),
    ]:
        client.index(
            index=INDEX_NAME,
            id=doc_id,
            body={"title": "Aardvark", "description": description, "keyword": keywords},
        )
    client.indices.refresh(index=INDEX_NAME)

    params = [
        ("q", "catalogsort"),
        ("keyword", "included"),
        ("keyword", "second"),
        ("sort", "title"),
        ("per_page", "2"),
    ]
    results = []
    after = None
    with patch("app.routes.interface", interface):
        for page in range(4):
            query = params + ([("after", after)] if after else [])
            response = db_client.get("/search", query_string=query)
            assert response.status_code == 200
            data = response.get_json()
            assert data["sort"] == "title"
            assert len(data["results"]) == 2
            results.extend(data["results"])
            after = data.get("after")
            assert bool(after) == (page < 3)

    assert [row["slug"] for row in results] == [
        f"title-{number}" for number in [3, 2, 1, 4, 5, 6, 8, 7]
    ]
    assert [row.get("title") for row in results] == [
        "alpha",
        "ALPHA",
        "alpha",
        "Beta",
        "The Zebra",
        "zebra",
        None,
        None,
    ]


@pytest.mark.parametrize("organization_page", [False, True])
def test_title_sort_selection_and_pagination_keep_search_state(
    interface_with_dataset, db_client, organization_page
):
    interface = interface_with_dataset
    organization = interface.db.query(Organization).first()
    path = f"/organization/{organization.slug}" if organization_page else "/"
    params = [
        ("q", "health"),
        ("keyword", "health"),
        ("sort", "title"),
        ("results", "1"),
    ]

    with patch("app.routes.interface", interface):
        response = db_client.get(path, query_string=params)

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    option = soup.select_one('#sort-select option[value="title"]')
    assert option.get_text() == "Title (A-Z)"
    assert option.has_attr("selected")
    assert soup.select_one('input[name="sort"][type="hidden"]')["value"] == "title"
    form = soup.select_one("#filter-form")
    assert form.select_one('input[name="after"]') is None
    more = soup.select_one("button[hx-get]")
    assert more is not None
    for attribute in ["hx-get", "hx-push-url"]:
        query = parse_qs(urlparse(more[attribute]).query)
        assert query["sort"] == ["title"]
        assert query["q"] == ["health"]
        assert query["keyword"] == ["health"]
    assert "after" in parse_qs(urlparse(more["hx-get"]).query)
