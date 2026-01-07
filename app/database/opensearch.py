import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, TypeVar

from botocore.credentials import Credentials
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection, helpers
from opensearchpy.exceptions import ConnectionTimeout

from .constants import DEFAULT_PER_PAGE

logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT_RETRIES = 3
DEFAULT_TIMEOUT_BACKOFF_BASE = 2.0
DEFAULT_DELETE_REQUEST_TIMEOUT_SECONDS = 120
DEFAULT_REFRESH_REQUEST_TIMEOUT_SECONDS = 120


@dataclass
class SearchResult:
    total: int
    results: list[dict]
    search_after: list

    def __len__(self):
        """Length of this is the length of results."""
        return len(self.results)

    @classmethod
    def empty(cls):
        """Return an empty search result instance."""
        return cls(total=0, results=[], search_after=None)

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
        hits = result_dict["hits"]["hits"]
        results = [
            {
                **each["_source"],
                "_score": each.get("_score"),
                "_sort": each.get("sort"),
            }
            for each in hits
        ]
        if per_page_hint:
            if len(results) > per_page_hint:
                # more results than we need to return, there will be results if we
                # use search_after from the last result we return
                search_after = hits[per_page_hint - 1]["sort"]
                results = results[:per_page_hint]
            else:
                # no extra results, so no further search results
                # return everything and None for search_after
                search_after = None
        else:
            # no page size hint
            if hits:
                # return everything we have and the search_after from the last
                # result
                search_after = hits[-1]["sort"]
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


T = TypeVar("T")


class OpenSearchInterface:

    INDEX_NAME = "datasets"
    TEXT_ANALYZER = "datagov_text"
    STOP_FILTER = "datagov_stop"

    # Custom analyzer removes English stop words so connective terms like
    # "and" do not reduce search recall.
    SETTINGS = {
        "analysis": {
            "filter": {
                STOP_FILTER: {
                    "type": "stop",
                    "stopwords": "_english_",
                }
            },
            "analyzer": {
                TEXT_ANALYZER: {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", STOP_FILTER],
                }
            },
        }
    }

    MAPPINGS = {
        "properties": {
            "title": {
                "type": "text",
                "analyzer": TEXT_ANALYZER,
                "search_analyzer": TEXT_ANALYZER,
            },
            "slug": {"type": "keyword"},
            "last_harvested_date": {"type": "date"},
            "dcat": {
                "type": "nested",
                "properties": {
                    "modified": {"type": "keyword"},  # Ensure modified is always text
                    "issued": {"type": "keyword"},  # Also ensure issued is text
                },
            },
            "description": {
                "type": "text",
                "analyzer": TEXT_ANALYZER,
                "search_analyzer": TEXT_ANALYZER,
            },
            "publisher": {
                "type": "text",
                "analyzer": TEXT_ANALYZER,
                "search_analyzer": TEXT_ANALYZER,
            },
            # Opensearch natively handles array-valued properties
            # Use multi-field mapping: text for search, keyword for aggregations
            "keyword": {
                "type": "text",
                "analyzer": TEXT_ANALYZER,
                "search_analyzer": TEXT_ANALYZER,
                "fields": {
                    "raw": {"type": "keyword"}  # For exact matching and aggregations
                },
            },
            "theme": {
                "type": "text",
                "analyzer": TEXT_ANALYZER,
                "search_analyzer": TEXT_ANALYZER,
            },
            "identifier": {
                "type": "text",
                "analyzer": TEXT_ANALYZER,
                "search_analyzer": TEXT_ANALYZER,
            },
            "has_spatial": {"type": "boolean"},  # Whether dataset has spatial data
            "popularity": {"type": "integer"},
            # keyword for exact matches
            "organization": {
                "type": "nested",
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {
                        "type": "text",
                        "analyzer": TEXT_ANALYZER,
                        "search_analyzer": TEXT_ANALYZER,
                    },
                    "description": {
                        "type": "text",
                        "analyzer": TEXT_ANALYZER,
                        "search_analyzer": TEXT_ANALYZER,
                    },
                    "slug": {"type": "keyword"},
                    "organization_type": {"type": "keyword"},
                },
            },
            "spatial_shape": {"type": "geo_shape"},
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
            timeout=10,
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
            timeout=60,
        )

    def _ensure_index(self):
        """Ensure that the named index named exists.

        Creates the index with the correct mapping if it does not exist.
        """
        if not self.client.indices.exists(index=self.INDEX_NAME):
            body = {"mappings": self.MAPPINGS}
            if self.SETTINGS:
                body["settings"] = self.SETTINGS
            self.client.indices.create(index=self.INDEX_NAME, body=body)

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

    @staticmethod
    def _normalize_dcat_dates(dcat: dict) -> dict:
        """Normalize date fields in DCAT to ensure they're always strings.

        dcat: DCAT dictionary that may contain datetime objects

        the returned value is the modified dcat dict.
        """
        # Create a copy to avoid mutating the original
        normalized_dcat = dcat.copy()

        # Fields that should be converted to strings
        date_fields = ["modified", "issued", "temporal"]

        for field in date_fields:
            if field in normalized_dcat:
                value = normalized_dcat[field]
                if isinstance(value, (datetime, date)):
                    normalized_dcat[field] = value.isoformat()
                elif value is not None and not isinstance(value, str):
                    # Convert any other non-string type to string
                    normalized_dcat[field] = str(value)

        return normalized_dcat

    def dataset_to_document(self, dataset):
        """Map a dataset into a document for indexing.

        Document is a JSON object used in a bulk insert so it needs to include
        an `_id` and `_index` property. We use the dataset's `id` for the
        document's `_id`.
        """
        # Check if dataset has spatial data
        spatial_value = dataset.dcat.get("spatial")
        has_spatial = bool(spatial_value and str(spatial_value).strip()) or (
            dataset.translated_spatial is not None
        )

        # Normalize DCAT dates to ensure they're strings
        normalized_dcat = self._normalize_dcat_dates(dataset.dcat)

        return {
            "_index": self.INDEX_NAME,
            "_id": dataset.id,
            "title": dataset.dcat.get("title", ""),
            "slug": dataset.slug,
            "last_harvested_date": dataset.last_harvested_date.isoformat(),
            "description": dataset.dcat.get("description", ""),
            "publisher": dataset.dcat.get("publisher", {}).get("name", ""),
            "dcat": normalized_dcat,
            # Opensearch handles array-value properties
            "keyword": dataset.dcat.get("keyword", []),
            "theme": dataset.dcat.get("theme", []),
            "identifier": dataset.dcat.get("identifier", ""),
            "has_spatial": has_spatial,
            "organization": dataset.organization.to_dict(),
            "popularity": (
                dataset.popularity if dataset.popularity is not None else None
            ),
            "spatial_shape": dataset.translated_spatial,
        }

    def _run_with_timeout_retry(
        self,
        action: Callable[[], T],
        *,
        action_name: str,
        timeout_retries: int,
        timeout_backoff_base: float,
    ) -> T:
        attempt = 0

        while True:
            try:
                return action()
            except ConnectionTimeout as exc:
                attempt += 1
                if attempt > timeout_retries:
                    logger.error(
                        "%s timed out after %s retries; giving up.",
                        action_name,
                        timeout_retries,
                        exc_info=exc,
                    )
                    raise

                wait_seconds = min(timeout_backoff_base**attempt, 60)
                logger.warning(
                    "%s timed out (attempt %s/%s); retrying in %.1f seconds.",
                    action_name,
                    attempt,
                    timeout_retries,
                    wait_seconds,
                    exc_info=exc,
                )
                time.sleep(wait_seconds)

    def delete_all_datasets(
        self,
        timeout_retries: int = DEFAULT_TIMEOUT_RETRIES,
        timeout_backoff_base: float = DEFAULT_TIMEOUT_BACKOFF_BASE,
        request_timeout: int = DEFAULT_DELETE_REQUEST_TIMEOUT_SECONDS,
    ):
        """Delete all documents from our index."""

        def _do_delete():
            return self.client.delete_by_query(
                index=self.INDEX_NAME,
                body={"query": {"match_all": {}}},
                # allow long-running deletions to finish before timing out
                request_timeout=request_timeout,
            )

        self._run_with_timeout_retry(
            _do_delete,
            action_name="OpenSearch delete_by_query",
            timeout_retries=timeout_retries,
            timeout_backoff_base=timeout_backoff_base,
        )

    def _refresh(
        self,
        timeout_retries: int = DEFAULT_TIMEOUT_RETRIES,
        timeout_backoff_base: float = DEFAULT_TIMEOUT_BACKOFF_BASE,
        request_timeout: int = DEFAULT_REFRESH_REQUEST_TIMEOUT_SECONDS,
    ):
        """Refresh our index."""

        def _do_refresh():
            return self.client.indices.refresh(
                index=self.INDEX_NAME, request_timeout=request_timeout
            )

        self._run_with_timeout_retry(
            _do_refresh,
            action_name="OpenSearch refresh",
            timeout_retries=timeout_retries,
            timeout_backoff_base=timeout_backoff_base,
        )

    def index_datasets(
        self,
        dataset_iter,
        refresh_after=True,
        timeout_retries: int = DEFAULT_TIMEOUT_RETRIES,
        timeout_backoff_base: float = DEFAULT_TIMEOUT_BACKOFF_BASE,
    ):
        """Index an iterator of dataset objects into OpenSearch.

        Returns a tuple of number of (succeeded, failed) items.
        """
        datasets = getattr(dataset_iter, "items", dataset_iter)
        documents = [self.dataset_to_document(dataset) for dataset in datasets]

        def _stream_bulk():
            succeeded_local = 0
            failed_local = 0
            errors = []
            for success, item in helpers.streaming_bulk(
                self.client,
                documents,
                raise_on_error=False,
                # retry when we are making too many requests
                max_retries=8,
            ):
                index_info = item.get("index")
                index_error = index_info.get("error")
                if success:
                    succeeded_local += 1
                    if item["index"]["result"].lower() not in ["created", "updated"]:
                        if index_info:
                            errors.append(
                                {
                                    "dataset_id": index_info.get("_id"),
                                    "status_code": index_info["_shards"].get("status"),
                                    "error_type": "Silent Error",
                                    "error_reason": "Unknown",
                                    "caused_by": index_info,
                                }
                            )
                else:
                    failed_local += 1
                    if index_info and index_error:
                        errors.append(
                            {
                                "dataset_id": index_info.get("_id"),
                                "status_code": index_info.get("status"),
                                "error_type": index_error.get("type"),
                                "error_reason": index_error.get("reason"),
                                "caused_by": index_error.get("caused_by"),
                            }
                        )
            return succeeded_local, failed_local, errors

        succeeded, failed, errors = self._run_with_timeout_retry(
            _stream_bulk,
            action_name="OpenSearch bulk index",
            timeout_retries=timeout_retries,
            timeout_backoff_base=timeout_backoff_base,
        )

        if refresh_after:
            self._refresh()

        return (succeeded, failed, errors)

    def _build_sort_clause(self, sort_by: str) -> list[dict]:
        """Return the OpenSearch sort clause for the requested key."""
        sort_key = (sort_by or "relevance").lower()

        if sort_key == "popularity":
            return [
                {"popularity": {"order": "desc", "missing": "_last"}},
                {"_score": {"order": "desc"}},
                {"_id": {"order": "desc"}},
            ]

        # Default to relevance sorting with popularity as a tie-breaker
        return [
            {"_score": {"order": "desc"}},
            {"popularity": {"order": "desc", "missing": "_last"}},
            {"_id": {"order": "desc"}},
        ]

    def search(
        self,
        query,
        per_page=DEFAULT_PER_PAGE,
        org_id=None,
        search_after: list = None,
        org_types=None,
        spatial_filter=None,
        spatial_geometry=None,
        spatial_within=True,
        sort_by: str = "relevance",
        keywords: list[str] = None,
    ) -> SearchResult:
        """Search our index for a query string.

        We use OpenSearch's multi-match to match our single query string
        against many fields. We use the "boost" numbers to score some fields
        higher than others.

        If the org_id argument is given then we only return search results
        that are in that organization.

        If keywords are provided, only datasets with those exact keywords will
        be returned (exact match on keyword.raw field).

        spatial_filter can be "geospatial" or "non-geospatial" to filter
        datasets by presence of spatial data.

        spatial_geometry is a GeoJSON object which will be used to search for
        datasets

        spatial_within is a flag for how to interpret spatial_geometry. If
        spatial_within is True then matching datasets must be completely
        WITHIN the specified spatial_geometry. If spatial_within is False then
        matching datasets only need to INTERSECT the specified
        spatial_geometry.

        We pass the `after` argument through to OpenSearch. It should be the
        value of the last `_sort` field from a previous search result with the
        same query.
        """
        if query and query.strip():
            base_query: dict[str, Any] = {
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
        else:
            base_query = {"match_all": {}}

        search_body = {
            "query": base_query,
            "sort": self._build_sort_clause(sort_by),
            # ask for one more to help with pagination, see
            # from_opensearch_result above
            "size": per_page + 1,
        }

        # Build filter list for bool query
        filters = []

        # Add keyword filter (exact match) - AND logic
        # Each keyword gets its own term filter, so all must match
        if keywords:
            for keyword in keywords:
                filters.append({"term": {"keyword.raw": keyword}})

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

        # Add spatial filter
        if spatial_filter == "geospatial":
            filters.append({"term": {"has_spatial": True}})
        elif spatial_filter == "non-geospatial":
            filters.append({"term": {"has_spatial": False}})

        # Add spatial_geojson filter
        if spatial_geometry is not None:
            filters.append(
                {
                    "geo_shape": {
                        "spatial_shape": {
                            "shape": spatial_geometry,
                            "relation": "WITHIN" if spatial_within else "INTERSECTS",
                        }
                    }
                }
            )

        # Apply filters if any exist
        if filters:
            search_body["query"] = {
                "bool": {
                    "filter": filters,
                    "must": [
                        # use the previous query in here
                        base_query,
                    ],
                }
            }
        if search_after is not None:
            search_body["search_after"] = search_after

        print("QUERY:", search_body)
        result_dict = self.client.search(index=self.INDEX_NAME, body=search_body)
        print("OPENSEARCH:", result_dict)
        return SearchResult.from_opensearch_result(result_dict, per_page_hint=per_page)

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
        buckets = (
            result.get("aggregations", {}).get("unique_keywords", {}).get("buckets", [])
        )

        return [
            {"keyword": bucket["key"], "count": bucket["doc_count"]}
            for bucket in buckets
        ]

    def get_organization_counts(self, size=100, min_doc_count=1) -> list[dict]:
        """Aggregate datasets by organization slug to get counts."""
        agg_body = {
            "size": 0,
            "aggs": {
                "organizations": {
                    "nested": {"path": "organization"},
                    "aggs": {
                        "by_slug": {
                            "terms": {
                                "field": "organization.slug",
                                "size": size,
                                "min_doc_count": min_doc_count,
                                "order": {"_count": "desc"},
                            }
                        }
                    },
                }
            },
        }

        result = self.client.search(index=self.INDEX_NAME, body=agg_body)
        buckets = (
            result.get("aggregations", {})
            .get("organizations", {})
            .get("by_slug", {})
            .get("buckets", [])
        )

        return [
            {"slug": bucket["key"], "count": bucket["doc_count"]}
            for bucket in buckets
        ]

    def count_all_datasets(self) -> int:
        """
        Get the total count of all datasets in the index.
        """
        try:
            result = self.client.count(index=self.INDEX_NAME)
            return result.get("count", 0)
        except Exception as e:
            logger.error(f"Error counting datasets in OpenSearch: {e}")
            return 0
