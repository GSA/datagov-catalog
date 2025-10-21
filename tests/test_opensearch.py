from app.models import Dataset


class TestOpenSearch:

    def test_index_and_search_datasets(self, interface_with_dataset, opensearch_client):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        opensearch_client.index_datasets(dataset_iterator)
        # the test dataset has title "test"
        results = opensearch_client.search("test")
        assert len(results) > 0
