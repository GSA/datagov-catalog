import pytest

from app.database import OpenSearchInterface
from app.models import Dataset


class TestOpenSearch:

    def test_bad_host_arguments(self):
        with pytest.raises(ValueError):
            # no hostnames
            OpenSearchInterface()

        with pytest.raises(ValueError):
            # both hostnames
            OpenSearchInterface(test_host="not-empty", aws_host="also-not-empty")

    def test_index_and_search_datasets(self, interface_with_dataset, opensearch_client):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        opensearch_client.index_datasets(dataset_iterator)
        # the test dataset has title "test"
        result_obj = opensearch_client.search("test")
        assert len(result_obj.results) > 0

    def test_index_and_search_other_fields(
        self, interface_with_dataset, opensearch_client
    ):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        opensearch_client.index_datasets(dataset_iterator)
        # One of the Americorps datasets has tnxs-meph in an identifier
        result_obj = opensearch_client.search("tnxs-meph")
        assert len(result_obj.results) > 0


def test_relevance_sort_uses_popularity_tie_breaker():
    client = OpenSearchInterface.__new__(OpenSearchInterface)
    sort_clause = client._build_sort_clause("relevance")
    assert sort_clause == [
        {"_score": {"order": "desc"}},
        {"popularity": {"order": "desc", "missing": "_last"}},
        {"_id": {"order": "desc"}},
    ]
