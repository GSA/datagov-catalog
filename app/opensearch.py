import os

from opensearchpy import OpenSearch, helpers

OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST")


class OpenSearchInterface:

    INDEX_NAME = "datasets"

    MAPPINGS = {"properties": {"title": {"type": "text"}}}

    @staticmethod
    def _create_opensearch_client(host):
        """Get an OpenSearch client instance configured for our cluster."""
        return OpenSearch(
            hosts=[{"host": host, "port": 9200}],
            http_compress=True,  # enables gzip compression for request bodies
            http_auth=("admin", "admin"),
            use_ssl=True,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
        )

    def _ensure_index(self):
        """Ensure that the named index named exists.

        Creates the index with the correct mapping if it does not exist.
        """
        if not self.client.indices.exists(index=self.INDEX_NAME):
            self.client.indices.create(
                index=self.INDEX_NAME, body={"mappings": self.MAPPINGS}
            )

    def __init__(self, host=OPENSEARCH_HOST):
        """Interface for our OpenSearch cluster."""

        self.client = self._create_opensearch_client(host)
        self._ensure_index()

    def dataset_to_document(self, dataset):
        """Map a dataset into a document for indexing.

        Document is a JSON object used in a bulk insert so it needs to include
        an `_id` and `_index` property. We use the dataset's `id` for the
        document's `_id`.
        """
        return {
            "_index": self.INDEX_NAME,
            "_id": dataset.id,
            "title": dataset.dcat.get("title", ""),
        }

    def index_datasets(self, dataset_iter):
        """Index an iterator of dataset objects into OpenSearch.

        Returns a tuple of number of (succeeded, failed) items.
        """
        succeeded = 0
        failed = 0
        for success, item in helpers.streaming_bulk(
            self.client, map(self.dataset_to_document, dataset_iter)
        ):
            if success:
                succeeded += 1
            else:
                failed += 1

        self.client.indices.refresh(index=self.INDEX_NAME)
        return (succeeded, failed)

    def search(self, query):
        """Search our index for a query string.

        TODO: make a better search query weighted across many fields.
        """
        search_body = {
            "query": {"match": {"title": query}},
            "size": 10,
        }
        return self.client.search(index=self.INDEX_NAME, body=search_body)["hits"][
            "hits"
        ]
