import pytest
from opensearchpy.exceptions import ConnectionTimeout

import app.database.opensearch as opensearch_module
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


def test_run_with_timeout_retry_eventual_success(monkeypatch):
    interface = OpenSearchInterface.__new__(OpenSearchInterface)
    monkeypatch.setattr(opensearch_module.time, "sleep", lambda _: None)

    attempts = {"count": 0}

    def _action():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ConnectionTimeout("TIMEOUT")
        return "done"

    result = interface._run_with_timeout_retry(
        _action,
        action_name="test action",
        timeout_retries=3,
        timeout_backoff_base=2.0,
    )

    assert result == "done"
    assert attempts["count"] == 3


def test_run_with_timeout_retry_exhausted(monkeypatch):
    interface = OpenSearchInterface.__new__(OpenSearchInterface)
    monkeypatch.setattr(opensearch_module.time, "sleep", lambda _: None)

    def _action():
        raise ConnectionTimeout("TIMEOUT")

    with pytest.raises(ConnectionTimeout):
        interface._run_with_timeout_retry(
            _action,
            action_name="test action",
            timeout_retries=2,
            timeout_backoff_base=2.0,
        )
