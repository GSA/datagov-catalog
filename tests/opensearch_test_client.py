"""Test-only OpenSearch client with the canonical harvester index writer."""

from app.database.opensearch import OpenSearchInterface
from tests.vendor.opensearch_index import OpenSearchInterface as IndexWriter


class TestOpenSearchInterface(OpenSearchInterface, IndexWriter):
    """Combine catalog reads with the vendored harvester writer for tests."""

    __test__ = False

    def __init__(self, test_host="localhost", aws_host=None):
        OpenSearchInterface.__init__(self, test_host=test_host, aws_host=aws_host)
        self._ensure_index()

    def delete_all_datasets(self):
        return self.client.delete_by_query(
            index=self.INDEX_NAME,
            body={"query": {"match_all": {}}},
            request_timeout=120,
        )

    def recreate_index(self):
        self.client.indices.delete(index=self.INDEX_NAME, ignore=[404])
        self._ensure_index()
