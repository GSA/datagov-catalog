import pytest

from app.models import Dataset
from app.opensearch import OpenSearchInterface


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
        results = opensearch_client.search("test")
        assert len(results) > 0
