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

    def test_search_spatial_geometry_intersects(
        self, interface_with_dataset, opensearch_client
    ):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        opensearch_client.index_datasets(dataset_iterator)
        # This point is inside the polygon of the test dataset
        result_obj = opensearch_client.search(
            "",
            spatial_geometry={"type": "point", "coordinates": [-75, 40]},
            spatial_within=False,
        )
        assert len(result_obj.results) > 0

    def test_search_spatial_geometry_within(
        self, interface_with_dataset, opensearch_client
    ):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        opensearch_client.index_datasets(dataset_iterator)
        # This polygon contains the whole test dataset (and planet)
        result_obj = opensearch_client.search(
            "",
            spatial_geometry={
                "type": "polygon",
                "coordinates": [
                    [[-180, -90], [180, -90], [180, 90], [-180, 90], [-180, -90]]
                ],
            },
            spatial_within=True,
        )
        assert len(result_obj.results) > 0

    def test_search_spatial_geometry_intersects_not_within(
        self, interface_with_dataset, opensearch_client
    ):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        opensearch_client.index_datasets(dataset_iterator)
        # This polygon intersects the test dataset but doesn't contain it
        polygon = {
            "type": "polygon",
            "coordinates": [[[-85, 30], [-85, 40], [-75, 40], [-75, 30], [-85, 30]]],
        }
        result_obj = opensearch_client.search(
            "", spatial_geometry=polygon, spatial_within=True
        )
        assert len(result_obj.results) == 0

        result_obj = opensearch_client.search(
            "", spatial_geometry=polygon, spatial_within=False
        )
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
