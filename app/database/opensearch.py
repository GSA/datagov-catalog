import base64
import json
import os
from dataclasses import dataclass

from botocore.credentials import Credentials
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection, helpers

from .constants import DEFAULT_PER_PAGE


@dataclass
class SearchResult:
    total: int
    results: list[dict]
    search_after: list

    def __len__(self):
        """Length of this is the length of results."""
        return len(self.results)

    @classmethod
    def from_opensearch_result(cls, result_dict: dict, per_page_hint=0):
        """Make a results object from the result of an OpenSearch query.

        To know if we should give a `search_after` in the result, we need
        a hint for how many results "should" have been on the page and if
        there is more than that in this result, then we should give a
        value for search_after.

        In the `search` method we asked for one more than the per_page size
        to determine if there will be any more results left for another call.
        """

        total = result_dict["hits"]["total"]["value"]
        results = [each["_source"] for each in result_dict["hits"]["hits"]]
        if per_page_hint:
            if len(results) > per_page_hint:
                # more results than we need to return, there will be results if we
                # use search_after from the last result we return
                search_after = result_dict["hits"]["hits"][per_page_hint - 1]["sort"]
                results = results[:per_page_hint]
            else:
                # no extra results, so no further search results
                # return everything and None for search_after
                search_after = None
        else:
            # no page size hint
            if results:
                # return everything we have and the search_after from the last
                # result
                search_after = result_dict["hits"]["hits"][-1]["sort"]
            else:
                # no results in the list
                search_after = None

        return cls(
            total=total,
            results=results,
            search_after=search_after,
        )

    def search_after_obscured(self):
        """An encoded string representation of self.search_after.

        If self.search_after is None, don't encode it, just return None.
        """
        if self.search_after is None:
            return None
        return base64.urlsafe_b64encode(
            json.dumps(self.search_after, separators=(",", ":")).encode("utf-8")
        ).decode("utf-8")

    @staticmethod
    def decode_search_after(encoded_after):
        """Decode the encoded representation of self.search_after."""
        return json.loads(base64.urlsafe_b64decode(encoded_after).decode("utf-8"))


class OpenSearchInterface:

    INDEX_NAME = "datasets"

    MAPPINGS = {
        "properties": {
            "title": {"type": "text"},
            "slug": {"type": "keyword"},
            "dcat": {"type": "nested"},
            "description": {"type": "text"},
            "publisher": {"type": "text"},
            # Opensearch natively handles array-valued properties
            "keyword": {"type": "text"},
            "theme": {"type": "text"},
            "identifier": {"type": "text"},
            # keyword for exact matches
            "organization": {
                "type": "nested",
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {"type": "text"},
                    "description": {"type": "text"},
                    "slug": {"type": "keyword"},
                    "organization_type": {"type": "keyword"},
                },
            },
        }
    }

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

    @classmethod
    def from_environment(cls):
        """Factory method to return a best-guess instance from environment variables.

        Sniffs the OPENSEARCH_HOST environment variable to decide whether to
        init with aws_host or test_host.
        """
        opensearch_host = os.getenv("OPENSEARCH_HOST")
        if opensearch_host.endswith("es.amazonaws.com"):
            return cls(aws_host=opensearch_host)
        else:
            return cls(test_host=opensearch_host)

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
            "slug": dataset.slug,
            "description": dataset.dcat.get("description", ""),
            "publisher": dataset.dcat.get("publisher", {}).get("name", ""),
            "dcat": dataset.dcat,
            # Opensearch handles array-value properties
            "keyword": dataset.dcat.get("keyword", []),
            "theme": dataset.dcat.get("theme", []),
            "identifier": dataset.dcat.get("identifier", ""),
            "organization": dataset.organization.to_dict(),
        }

    def delete_all_datasets(self):
        """Delete all documents from our index."""
        self.client.delete_by_query(
            index=self.INDEX_NAME, body={"query": {"match_all": {}}}
        )

    def _refresh(self):
        """Refresh our index."""
        self.client.indices.refresh(index=self.INDEX_NAME)

    def index_datasets(self, dataset_iter, refresh_after=True):
        """Index an iterator of dataset objects into OpenSearch.

        Returns a tuple of number of (succeeded, failed) items.
        """
        succeeded = 0
        failed = 0
        for success, item in helpers.streaming_bulk(
            self.client,
            map(self.dataset_to_document, dataset_iter),
            raise_on_error=False,
            # retry when we are making too many requests
            max_retries=8,
        ):
            if success:
                succeeded += 1
            else:
                failed += 1

        if refresh_after:
            self._refresh()

        return (succeeded, failed)

    def search(
        self, query, per_page=DEFAULT_PER_PAGE, org_id=None, search_after: list = None
    ) -> SearchResult:
        """Search our index for a query string.

        We use OpenSearch's multi-match to match our single query string
        against many fields. We use the "boost" numbers to score some fields
        higher than others.

        If the org_id argument is given then we only return search results
        that are in that organization.

        We pass the `after` argument through to OpenSearch. It should be the
        value of the last `_sort` field from a previous search result with the
        same query.
        """
        search_body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "type": "most_fields",
                    "fields": [
                        "title^5",
                        "description^3",
                        "publisher^3",
                        "keyword^2",
                        "theme",
                        "identifier",
                    ],
                    "operator": "AND",
                    "zero_terms_query": "all",
                }
            },
            "sort": [
                {"_score": {"order": "desc"}},
                {"_id": {"order": "desc"}},
            ],
            # ask for one more to help with pagination, see
            # from_opensearch_result above
            "size": per_page + 1,
        }
        if org_id is not None:
            # need to add a filter query alongside the previous full-text
            # query
            search_body["query"] = {
                "bool": {
                    "filter": [
                        {
                            "nested": {
                                "path": "organization",
                                "query": {
                                    "term": {"organization.id": org_id},
                                },
                            },
                        },
                    ],
                    "must": [
                        # use the previous query in here
                        search_body["query"],
                    ],
                }
            }
        if search_after is not None:
            search_body["search_after"] = search_after

        result_dict = self.client.search(index=self.INDEX_NAME, body=search_body)
        print("OPENSEARCH:", result_dict)
        return SearchResult.from_opensearch_result(result_dict, per_page_hint=per_page)
