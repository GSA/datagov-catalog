import os

from botocore.credentials import Credentials
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection, helpers


class OpenSearchInterface:

    INDEX_NAME = "datasets"

    MAPPINGS = {"properties": {"title": {"type": "text"}}}

    @staticmethod
    def _create_test_opensearch_client(host):
        """Get an OpenSearch client instance configured for our test cluster."""
        return OpenSearch(
            hosts=[{"host": host, "port": 9200}],
            http_compress=True,  # enables gzip compression for request bodies
            http_auth=("admin", "admin"),
            use_ssl=True,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
        )

    @staticmethod
    def _create_aws_opensearch_client(host):
        """Get an OpenSearch client instance configured for an AWS cluster.

        Credentials are fetched from the environment in the
        environment variables OPENSEARCH_ACCESS_KEY and OPENSEARCH_SECRET_KEY
        """
        access_key = os.getenv("OPENSEARCH_ACCESS_KEY")
        secret_key = os.getenv("OPENSEARCH_SECRET_KEY")
        auth = AWSV4SignerAuth(
            Credentials(access_key=access_key, secret_key=secret_key),
            "us-gov-west-1",
            "es",
        )
        return OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            pool_maxsize=20,
        )

    def _ensure_index(self):
        """Ensure that the named index named exists.

        Creates the index with the correct mapping if it does not exist.
        """
        if not self.client.indices.exists(index=self.INDEX_NAME):
            self.client.indices.create(
                index=self.INDEX_NAME, body={"mappings": self.MAPPINGS}
            )

    def __init__(self, test_host=None, aws_host=None):
        """Interface for our OpenSearch cluster.

        One of `test_host` or `aws_host` must be specified, but not both. The
        `test_host` will be opened with HTTPS on port 9200 but no certificate
        verification and default username/password.

        Using `aws_host` will use port 443 and request signing with AWS
        credentials.
        """

        if aws_host is not None:
            if test_host is not None:
                # can't specify both
                raise ValueError("Cannot specify both test_host and aws_host")
            else:
                self.client = self._create_aws_opensearch_client(aws_host)
        else:
            if test_host is not None:
                self.client = self._create_test_opensearch_client(test_host)
            else:
                # nothing specified, not allowed
                raise ValueError("Must specify either test_host or aws_host")

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
