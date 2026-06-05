import time
from datetime import date, datetime
from typing import Callable, TypeVar

from flask import url_for
from opensearchpy import helpers
from opensearchpy.exceptions import ConnectionTimeout

from app.database.opensearch import OpenSearchInterface

T = TypeVar("T")

DEFAULT_TIMEOUT_RETRIES = 3
DEFAULT_TIMEOUT_BACKOFF_BASE = 2.0
DEFAULT_REFRESH_REQUEST_TIMEOUT_SECONDS = 120
DEFAULT_DELETE_REQUEST_TIMEOUT_SECONDS = 120


def normalize_dcat_dates(dcat: dict) -> dict:
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


def create_harvest_record_url(dataset) -> str:
    """Generates a url to the harvest record."""
    return url_for("main.get_harvest_record", record_id=dataset.harvest_record_id)


def create_harvest_record_raw_url(dataset) -> str:
    """Generates a url to the raw harvest-record payload."""
    return url_for("main.get_harvest_record_raw", record_id=dataset.harvest_record_id)


def create_harvest_record_transformed_url(dataset) -> str:
    """Generates a url to the transformed harvest-record payload."""
    return url_for(
        "main.get_harvest_record_transformed", record_id=dataset.harvest_record_id
    )


def has_harvest_record_transformed(dataset) -> bool:
    """True when dataset's harvest record has a non-empty transformed payload."""
    record = getattr(dataset, "harvest_record", None)
    if record is None:
        return False

    transformed = getattr(record, "source_transform", None)
    if transformed is None:
        return False

    if isinstance(transformed, str) and not transformed.strip():
        return False

    return True


def dataset_to_document(dataset, index_name):
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
    normalized_dcat = normalize_dcat_dates(dataset.dcat)

    spatial_centroid = OpenSearchInterface._geometry_centroid(
        dataset.translated_spatial
    )

    document = {
        "_index": index_name,
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
        "distribution_titles": [
            dist["title"]
            for dist in (dataset.dcat.get("distribution") or [])
            if isinstance(dist, dict) and dist.get("title")
        ],
        "popularity": (dataset.popularity if dataset.popularity is not None else None),
        "spatial_shape": dataset.translated_spatial,
        "spatial_centroid": spatial_centroid,
        "harvest_record": create_harvest_record_url(dataset),
        "harvest_record_raw": create_harvest_record_raw_url(dataset),
    }
    if has_harvest_record_transformed(dataset):
        document["harvest_record_transformed"] = create_harvest_record_transformed_url(
            dataset
        )
    return document


def run_with_timeout_retry(
    action: Callable[[], T],
    *,
    timeout_retries: int,
    timeout_backoff_base: float,
) -> T:
    attempt = 0

    while True:
        try:
            return action()
        # ruff: noqa: F841
        except ConnectionTimeout as exc:
            attempt += 1
            if attempt > timeout_retries:
                raise

            wait_seconds = min(timeout_backoff_base**attempt, 60)
            time.sleep(wait_seconds)


def refresh(
    client,
    timeout_retries: int = DEFAULT_TIMEOUT_RETRIES,
    timeout_backoff_base: float = DEFAULT_TIMEOUT_BACKOFF_BASE,
    request_timeout: int = DEFAULT_REFRESH_REQUEST_TIMEOUT_SECONDS,
):
    """Refresh our index."""

    def _do_refresh():
        return client.client.indices.refresh(
            index=client.INDEX_NAME, request_timeout=request_timeout
        )

    run_with_timeout_retry(
        _do_refresh,
        timeout_retries=timeout_retries,
        timeout_backoff_base=timeout_backoff_base,
    )


def index_datasets(
    client,
    dataset_iter,
    refresh_after=True,
    timeout_retries: int = DEFAULT_TIMEOUT_RETRIES,
    timeout_backoff_base: float = DEFAULT_TIMEOUT_BACKOFF_BASE,
):
    """Index an iterator of dataset objects into OpenSearch.

    Returns a tuple of number of (succeeded, failed) items.
    """
    datasets = getattr(dataset_iter, "items", dataset_iter)
    documents = [
        dataset_to_document(dataset, client.INDEX_NAME) for dataset in datasets
    ]

    def _stream_bulk():
        succeeded_local = 0
        failed_local = 0
        errors = []
        for success, item in helpers.streaming_bulk(
            client.client,
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
                errors.append(item)
        return succeeded_local, failed_local, errors

    succeeded, failed, errors = run_with_timeout_retry(
        _stream_bulk,
        timeout_retries=timeout_retries,
        timeout_backoff_base=timeout_backoff_base,
    )

    if refresh_after:
        refresh(client)

    return (succeeded, failed, errors)


def delete_all_datasets(
    client,
    timeout_retries: int = DEFAULT_TIMEOUT_RETRIES,
    timeout_backoff_base: float = DEFAULT_TIMEOUT_BACKOFF_BASE,
    request_timeout: int = DEFAULT_DELETE_REQUEST_TIMEOUT_SECONDS,
):
    """Delete all documents from our index."""

    def _do_delete():
        return client.client.delete_by_query(
            index=client.INDEX_NAME,
            body={"query": {"match_all": {}}},
            # allow long-running deletions to finish before timing out
            request_timeout=request_timeout,
        )

    run_with_timeout_retry(
        _do_delete,
        timeout_retries=timeout_retries,
        timeout_backoff_base=timeout_backoff_base,
    )
