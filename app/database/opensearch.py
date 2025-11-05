import os
from dataclasses import dataclass

from botocore.credentials import Credentials
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection, helpers

from .constants import DEFAULT_PER_PAGE


@dataclass
class SearchResult:
    total: int
    results: list[dict]

    def __len__(self):
        """Length of this is the length of results."""
        return len(self.results)

    @classmethod
    def from_opensearch_result(cls, result_dict: dict):
        """Make a results object from the result of an OpenSearch query."""
        return cls(
            total=result_dict["hits"]["total"]["value"],
            results=[each["_source"] for each in result_dict["hits"]["hits"]],
        )


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
            # Use multi-field mapping: text for search, keyword for aggregations
            "keyword": {
                "type": "text",
                "fields": {
                    "raw": {"type": "keyword"}  # For exact matching and aggregations
                }
            },
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

    def index_datasets(self, dataset_iter):
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

        self.client.indices.refresh(index=self.INDEX_NAME)
        return (succeeded, failed)

    def search(
        self, query, per_page=DEFAULT_PER_PAGE, org_id=None, org_types=None
    ) -> SearchResult:
        """Search our index for a query string.

        We use OpenSearch's multi-match to match our single query string
        against many fields. We use the "boost" numbers to score some fields
        higher than others.

        If the org_id argument is given then we only return search results
        that are in that organization.
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
            "size": per_page,
        }

        # Build filter list for bool query
        filters = []

        if org_id is not None:
            filters.append(
                {
                    "nested": {
                        "path": "organization",
                        "query": {
                            "term": {"organization.id": org_id},
                        },
                    },
                }
            )

        if org_types is not None and len(org_types) > 0:
            filters.append(
                {
                    "nested": {
                        "path": "organization",
                        "query": {
                            "terms": {"organization.organization_type": org_types},
                        },
                    },
                }
            )

        # Apply filters if any exist
        if filters:
            search_body["query"] = {
                "bool": {
                    "filter": filters,
                    "must": [
                        # use the previous query in here
                        search_body["query"],
                    ],
                }
            }

        result_dict = self.client.search(index=self.INDEX_NAME, body=search_body)
        # print("OPENSEARCH:", result_dict)
        return SearchResult.from_opensearch_result(result_dict)

    def get_unique_keywords(self, size=100, min_doc_count=1) -> list[dict]:
        """
        Get unique keywords from all datasets with their document counts.
        """
        agg_body = {
            "size": 0,  # Don't return documents, just aggregations
            "aggs": {
                "unique_keywords": {
                    "terms": {
                        "field": "keyword.raw",
                        "size": size,
                        "min_doc_count": min_doc_count,
                        "order": {"_count": "desc"},
                    }
                }
            },
        }

        result = self.client.search(index=self.INDEX_NAME, body=agg_body)
        buckets = result.get("aggregations", {}).get("unique_keywords", {}).get("buckets", [])

        return [{"keyword": bucket["key"], "count": bucket["doc_count"]} for bucket in buckets]

    def search_by_keywords(
        self,
        keywords: list[str],
        query: str = "",
        per_page=DEFAULT_PER_PAGE,
        org_id=None,
        org_types=None,
    ) -> SearchResult:
        """
        Search datasets that have specific keywords (exact match).
        """
        # Build filter list
        filters = []

        # Add keyword filter (exact match)
        if keywords:
            filters.append({"terms": {"keyword.raw": keywords}})

        # Add org_id filter if provided
        if org_id is not None:
            filters.append(
                {
                    "nested": {
                        "path": "organization",
                        "query": {"term": {"organization.id": org_id}},
                    }
                }
            )

        # Add org_types filter if provided
        if org_types is not None and len(org_types) > 0:
            filters.append(
                {
                    "nested": {
                        "path": "organization",
                        "query": {"terms": {"organization.organization_type": org_types}},
                    }
                }
            )

        # Build the search body
        if query:
            # If there's a text query, combine with filters
            search_body = {
                "query": {
                    "bool": {
                        "must": [
                            {
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
                            }
                        ],
                        "filter": filters,
                    }
                },
                "sort": [
                    {"_score": {"order": "desc"}},
                    {"_id": {"order": "desc"}},
                ],
                "size": per_page,
            }
        else:
            # No text query, just filter by keywords
            search_body = {
                "query": {"bool": {"filter": filters}},
                "sort": [{"_id": {"order": "desc"}}],
                "size": per_page,
            }

        result_dict = self.client.search(index=self.INDEX_NAME, body=search_body)
        return SearchResult.from_opensearch_result(result_dict)