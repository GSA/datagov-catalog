import pytest

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
