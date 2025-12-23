import os
import posixpath
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional
from urllib.parse import urlparse

import click
from flask import Blueprint
from opensearchpy.exceptions import ConnectionTimeout, OpenSearchException
from opensearchpy.helpers import scan
from sqlalchemy.exc import OperationalError

from .database import CatalogDBInterface, OpenSearchInterface
from .models import Dataset, HarvestJob, HarvestRecord, HarvestSource, Organization
from .sitemap_s3 import (
    SitemapS3ConfigError,
    create_sitemap_s3_client,
    get_sitemap_s3_config,
)

search = Blueprint("search", __name__)
sitemap = Blueprint("sitemap", __name__)
testdata = Blueprint("testdata", __name__)

BASE_URL = os.getenv("SITEMAP_BASE_URL", "http://localhost:8080").rstrip("/")


def register_commands(app):
    app.register_blueprint(search)
    app.register_blueprint(sitemap)
    app.register_blueprint(testdata)


@testdata.cli.command("load_test_data")
def load_test_data():
    from tests.fixtures import fixture_data

    fixture = fixture_data()
    interface = CatalogDBInterface()

    for organization_data in fixture["organization"]:
        interface.db.add(Organization(**organization_data))
    interface.db.add(HarvestSource(**fixture["harvest_source"]))
    interface.db.add(HarvestJob(**fixture["harvest_job"]))
    interface.db.add(HarvestRecord(**fixture["harvest_record"]))
    for data in fixture["dataset"]:
        interface.db.add(Dataset(**data))
    interface.db.commit()


@search.cli.command("sync")
@click.argument("dataset_id_or_slug", required=False)
@click.option("--start-page", help="Number of page to start on", default=1)
@click.option("--per_page", help="Number of datasets per page", default=100)
@click.option(
    "--recreate-index",
    is_flag=True,
    help="Delete and recreate index with new schema",
    default=False,
)
def sync_opensearch(
    dataset_id_or_slug: Optional[str] = None,
    start_page: int = 1,
    per_page: int = 100,
    recreate_index: bool = False,
):
    """Sync datasets to the OpenSearch system.

    Provide a DATASET_ID_OR_SLUG argument to reindex a single dataset without
    touching the rest of the index.

    Use --recreate-index flag when you've updated the schema (e.g., added keyword.raw field)
    to delete the old index and create a new one with the updated mapping.

    Retries added for when we may have multiple jobs running and causes the sync to break.
    There are 3 exponential retries, the initial retry being 2 seconds.
    """

    # Retry configuration
    max_retries = 3
    retry_delay = 2.0

    client = OpenSearchInterface.from_environment()

    if dataset_id_or_slug:
        interface = CatalogDBInterface()
        if recreate_index:
            raise click.ClickException(
                "Cannot use --recreate-index when syncing a single dataset."
            )

        dataset = interface.get_dataset_by_id(dataset_id_or_slug)
        if dataset is None:
            dataset = interface.get_dataset_by_slug(dataset_id_or_slug)

        if dataset is None:
            raise click.ClickException(
                f"Dataset '{dataset_id_or_slug}' was not found by id or slug."
            )

        click.echo(
            f"Indexing dataset {dataset.id} (slug: {dataset.slug}) into OpenSearch..."
        )
        succeeded, failed = client.index_datasets([dataset])

        if failed:
            raise click.ClickException(
                f"Failed to index dataset {dataset.id}; see logs for details."
            )

        click.echo("Dataset indexed successfully.")
        return

    # empty the index and then refill it
    # THIS WILL CAUSE INCONSISTENT SEARCH RESULTS DURING THE PROCESS

    if recreate_index:
        click.echo("Deleting entire index to recreate with new schema...")
        try:
            client.client.indices.delete(index=client.INDEX_NAME)
            click.echo("Index deleted")
        except Exception as e:
            click.echo(f"Could not delete index (may not exist): {e}")

        # Recreate with new schema
        click.echo("Creating index with new schema...")
        client._ensure_index()
        click.echo("Index created with updated mapping")

        # Verify the new mapping
        mapping = client.client.indices.get_mapping(index=client.INDEX_NAME)
        keyword_mapping = mapping[client.INDEX_NAME]["mappings"]["properties"].get(
            "keyword", {}
        )
        has_raw = "fields" in keyword_mapping and "raw" in keyword_mapping["fields"]
        if has_raw:
            click.echo("Verified: keyword.raw field exists in new mapping")
        else:
            click.echo(
                "Warning: keyword.raw field not found in mapping - aggregations may not work"
            )
    else:
        click.echo("Emptying dataset index (keeping existing schema)...")
        client.delete_all_datasets()

    click.echo("Indexing...")

    # do our own pagination of the dataset query before calling into the
    # index_datasets method
    total_pages = Dataset.query.paginate(per_page=per_page).pages
    click.echo(f"Indexing {total_pages} pages of datasets...")

    try:
        # page numbers are 1-indexed
        for i in range(start_page, total_pages + 1):
            retry_count = 0
            last_exception = None

            while retry_count <= max_retries:
                try:
                    # Get the paginated dataset query
                    paginated_datasets = Dataset.query.paginate(
                        page=i, per_page=per_page
                    )

                    # Index the datasets
                    succeeded, failed = client.index_datasets(
                        paginated_datasets, refresh_after=False
                    )

                    # Success - break out of retry loop
                    click.echo(
                        f"Indexed page {i}/{total_pages} with {succeeded} successes and {failed} errors."
                    )
                    break

                except (OpenSearchException, ConnectionTimeout, OperationalError) as e:
                    last_exception = e
                    retry_count += 1

                    error_type = type(e).__name__

                    # Check if this is a PostgreSQL serialization failure
                    # Safely convert exception to string
                    try:
                        error_str = str(e)
                    except Exception:
                        error_str = repr(e)

                    is_serialization_error = (
                        isinstance(e, OperationalError)
                        and "conflict with recovery" in error_str
                    )

                    if retry_count <= max_retries:
                        # Calculate exponential backoff delay
                        wait_time = retry_delay * (2 ** (retry_count - 1))

                        click.echo(
                            f"Page {i}/{total_pages}: {error_type} - "
                            f"{'Database serialization conflict' if is_serialization_error else 'Error'} "
                            f"(attempt {retry_count}/{max_retries + 1}). "
                            f"Retrying in {wait_time:.1f} seconds..."
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        # Max retries exceeded
                        try:
                            error_msg = str(last_exception)
                        except Exception:
                            error_msg = repr(last_exception)
                        click.echo(
                            f"Page {i}/{total_pages}: Failed after {max_retries + 1} attempts. "
                            f"Last error: {error_type} - {error_msg[:200] if error_msg else 'Unknown error'}"
                        )
                        # Exit with error code
                        raise click.ClickException(
                            f"Sync failed after {max_retries + 1} attempts"
                        )

        click.echo("Refreshing index...")
        client._refresh()
        click.echo("Sync was successful")
    except click.ClickException:
        # Re-raise Click exceptions (these exit cleanly with proper exit code)
        raise
    except Exception as e:
        # Catch any other unexpected errors
        click.echo(f"Unexpected error during sync: {type(e).__name__}")
        raise click.ClickException(f"Sync failed: {type(e).__name__}")


@search.cli.command("compare")
@click.option(
    "--sample-size",
    default=10,
    show_default=True,
    help="How many example IDs to print for each discrepancy type.",
)
@click.option(
    "--fix",
    is_flag=True,
    help="Automatically index missing datasets and delete extra docs from OpenSearch.",
)
def compare_opensearch(sample_size: int, fix: bool):
    """Report (and optionally fix) dataset ID discrepancies between DB and OpenSearch."""

    interface = CatalogDBInterface()
    client = OpenSearchInterface.from_environment()

    click.echo("Collecting dataset IDs from DB…")
    db_ids = {row[0] for row in interface.db.query(Dataset.id).all()}
    click.echo(f"Database datasets: {len(db_ids)}")

    click.echo("Collecting document IDs from OpenSearch…")
    os_ids = {
        hit["_id"]
        for hit in scan(client.client, index=client.INDEX_NAME, _source=False)
    }
    click.echo(f"OpenSearch documents: {len(os_ids)}")

    missing = sorted(db_ids - os_ids)
    extra = sorted(os_ids - db_ids)

    click.echo(
        f"Missing in OpenSearch (should be indexed): {len(missing)}"
    )
    if missing:
        click.echo(
            "Example missing IDs: " + ", ".join(missing[:sample_size])
        )
    else:
        click.echo("Example missing IDs: none")

    click.echo(
        f"Extra in OpenSearch (should be deleted): {len(extra)}"
    )
    if extra:
        click.echo("Example extra IDs: " + ", ".join(extra[:sample_size]))
    else:
        click.echo("Example extra IDs: none")

    if not fix:
        return

    click.echo("\nFixing discrepancies…")

    if missing:
        click.echo(f"Indexing {len(missing)} missing datasets…")
        batch_size = 1000
        total_indexed = 0
        total_skipped = 0

        for batch_number, batch_ids in enumerate(
            (missing[i : i + batch_size] for i in range(0, len(missing), batch_size)),
            start=1,
        ):
            click.echo(
                f"  Batch {batch_number}: indexing {len(batch_ids)} dataset(s)…"
            )
            datasets = (
                interface.db.query(Dataset)
                .filter(Dataset.id.in_(batch_ids))
                .all()
            )

            found_ids = {dataset.id for dataset in datasets}
            skipped = [dataset_id for dataset_id in batch_ids if dataset_id not in found_ids]
            total_skipped += len(skipped)

            if skipped:
                click.echo(
                    "    Warning: Skipping missing DB IDs: "
                    + ", ".join(skipped[:sample_size])
                )

            if datasets:
                succeeded, failed = client.index_datasets(
                    datasets, refresh_after=False
                )
                total_indexed += succeeded
                if failed:
                    click.echo(
                        f"    Warning: {failed} dataset(s) failed to index in this batch."
                    )
            else:
                click.echo("    No datasets found for this batch; skipping.")

        click.echo(
            f"Indexed {total_indexed} datasets. Skipped {total_skipped} missing DB rows."
        )

    if extra:
        click.echo(f"Deleting {len(extra)} extra documents from OpenSearch…")
        deleted = 0
        batch_size = 1000
        for batch_number, batch_ids in enumerate(
            (extra[i : i + batch_size] for i in range(0, len(extra), batch_size)),
            start=1,
        ):
            click.echo(
                f"  Batch {batch_number}: deleting {len(batch_ids)} document(s)…"
            )
            for doc_id in batch_ids:
                try:
                    client.client.delete(index=client.INDEX_NAME, id=doc_id)
                    deleted += 1
                except Exception as exc:  # pragma: no cover - best-effort cleanup
                    click.echo(f"    Failed to delete document {doc_id}: {exc}")

        click.echo(f"Deleted {deleted} documents from OpenSearch.")

    if missing or extra:
        click.echo("Refreshing OpenSearch index…")
        client._refresh()
        click.echo("Done.")
    else:
        click.echo("Nothing to fix; datasets and index are already in sync.")


# ----------------------
# Sitemaps: Generate + Upload to S3
# ----------------------


def _sitemap_lastmod(dataset: Dataset) -> Optional[str]:
    dt = getattr(dataset, "last_harvested_date", None)
    if dt is None:
        return None
    try:
        return dt.date().isoformat()
    except Exception:
        return None


def _build_sitemap_chunk_xml(datasets: Iterable[Dataset]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for ds in datasets:
        # The app will serve these at /dataset/<slug>
        # Use absolute URLs with the public base
        loc = f"{BASE_URL}/dataset/{ds.slug}"
        lastmod = _sitemap_lastmod(ds)
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        if lastmod is not None:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines)


def _build_sitemap_index_xml(total_chunks: int) -> str:
    today = date.today().isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for idx in range(total_chunks):
        loc = f"{BASE_URL}/sitemap/sitemap-{idx}.xml"
        lines.append("  <sitemap>")
        lines.append(f"    <loc>{loc}</loc>")
        lines.append(f"    <lastmod>{today}</lastmod>")
        lines.append("  </sitemap>")
    lines.append("</sitemapindex>")
    return "\n".join(lines)


def _s3_client_and_config():
    try:
        config = get_sitemap_s3_config()
    except SitemapS3ConfigError as exc:
        raise click.ClickException(str(exc))

    s3 = create_sitemap_s3_client()
    return s3, config.bucket, config.prefix, config.index_key


@sitemap.cli.command("generate")
@click.option(
    "--chunk-size",
    type=int,
    default=lambda: int(os.getenv("SITEMAP_CHUNK_SIZE", "10000")),
    help="URLs per sitemap file (default 10000)",
)
def sitemap_generate(chunk_size: int):
    """Generate all dataset sitemaps and upload to S3.

    Requires env vars:
        SITEMAP_S3_BUCKET (required),
        optional SITEMAP_S3_PREFIX,
        SITEMAP_INDEX_KEY,
        SITEMAP_BASE_URL
    Uses AWS credentials from env vars.
    """
    s3, bucket, prefix, index_key = _s3_client_and_config()

    dbi = CatalogDBInterface()

    total = dbi.db.query(Dataset).count()
    total_chunks = (total + chunk_size - 1) // chunk_size if total else 0
    # Always create at least one chunk file so that routes and verification
    # have a consistent location even when there are no datasets yet.
    total_chunks = max(total_chunks, 1)
    click.echo(
        f"Total datasets: {total}; generating {total_chunks} chunk(s) of size {chunk_size}"
    )

    # order by last_harvested_date asc, then slug
    def get_window(offset: int, limit: int):
        return (
            dbi.db.query(Dataset)
            .order_by(
                Dataset.last_harvested_date.asc().nullslast(),
                Dataset.slug.asc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

    # upload each chunk whenever it is generated
    for idx in range(total_chunks):
        offset = idx * chunk_size
        datasets = get_window(offset, chunk_size)
        xml_body = _build_sitemap_chunk_xml(datasets)
        key = f"{prefix.rstrip('/')}/sitemap-{idx}.xml"
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=xml_body.encode("utf-8"),
            ContentType="application/xml",
        )
        click.echo(f"Uploaded {key} ({len(datasets)} URLs)")

    # upload sitemap index
    index_body = _build_sitemap_index_xml(total_chunks)
    s3.put_object(
        Bucket=bucket,
        Key=index_key,
        Body=index_body.encode("utf-8"),
        ContentType="application/xml",
    )
    click.echo(f"Uploaded {index_key}")


@sitemap.cli.command("verify")
@click.option(
    "--dry-run", is_flag=True, default=False, help="Show actions without deleting"
)
@click.option(
    "--max-age-hours",
    type=int,
    default=lambda: int(os.getenv("SITEMAP_MAX_AGE_HOURS", "1")),
    help="Fail if index or chunks are older than this many hours (default 1)",
)
@click.option(
    "--skip-freshness",
    is_flag=True,
    default=False,
    help="Skip timestamp freshness checks (only validates presence and cleans extras)",
)
def sitemap_verify(dry_run: bool, max_age_hours: int, skip_freshness: bool):
    """Verify sitemap chunks against the index and remove stale files.

    - Reads the sitemap index (sitemap.xml) from S3
    - Confirms each referenced chunk exists in S3
    - Deletes chunk files in the prefix that are not referenced by the index
    """
    s3, bucket, prefix, index_key = _s3_client_and_config()

    # Fetch index
    try:
        # Fetch index body; optionally fetch HEAD for timestamp when checking freshness
        obj = s3.get_object(Bucket=bucket, Key=index_key)
        body = obj["Body"].read()
        index_head = (
            s3.head_object(Bucket=bucket, Key=index_key) if not skip_freshness else None
        )
    except Exception as e:
        raise click.ClickException(f"Failed to fetch index {index_key}: {e}")

    # Parse index for <loc> values
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        raise click.ClickException(f"Invalid sitemap index XML: {e}")

    # Sitemap namespace handling (default namespace)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    loc_elems = root.findall(".//sm:loc", ns)
    expected_keys = set()
    for loc_el in loc_elems:
        loc_text = (loc_el.text or "").strip()
        if not loc_text:
            continue
        parsed = urlparse(loc_text)
        base = posixpath.basename(parsed.path)
        if not base:
            continue
        expected_keys.add(f"{prefix.rstrip('/')}/{base}")

    click.echo(f"Found {len(expected_keys)} expected chunk(s) in index")

    # Recency threshold
    now_utc = datetime.now(timezone.utc)
    threshold = now_utc - timedelta(hours=max_age_hours)

    # Check index recency (unless skipped)
    index_stale = False
    if not skip_freshness and index_head is not None:
        index_last_modified = index_head.get("LastModified")
        if (
            isinstance(index_last_modified, datetime)
            and index_last_modified < threshold
        ):
            index_stale = True
            click.echo(
                f"Index stale: {index_key} modified {index_last_modified.isoformat()} (threshold {threshold.isoformat()})"
            )

    # Verify existence of expected chunks
    missing = []
    old_chunks = []
    for key in sorted(expected_keys):
        try:
            head = s3.head_object(Bucket=bucket, Key=key)
            if not skip_freshness:
                lm = head.get("LastModified")
                if isinstance(lm, datetime) and lm < threshold:
                    old_chunks.append((key, lm))
        except Exception:
            missing.append(key)

    if missing:
        click.echo("Missing chunks:")
        for key in missing:
            click.echo(f"  - s3://{bucket}/{key}")
    else:
        click.echo("All referenced chunks exist.")

    if old_chunks and not skip_freshness:
        click.echo("Out-of-date chunks (older than max-age):")
        for key, lm in old_chunks:
            click.echo(f"  - s3://{bucket}/{key} (LastModified: {lm.isoformat()})")

    # List current chunks under prefix
    current_keys = set()
    continuation = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if continuation:
            kwargs["ContinuationToken"] = continuation
        resp = s3.list_objects_v2(**kwargs)
        for item in resp.get("Contents", []):
            key = item.get("Key")
            if (
                key
                and key.endswith(".xml")
                and posixpath.basename(key).startswith("sitemap-")
            ):
                current_keys.add(key)
        if resp.get("IsTruncated"):
            continuation = resp.get("NextContinuationToken")
        else:
            break

    stale = sorted(current_keys - expected_keys)
    if stale:
        click.echo("Stale chunks (not listed in index):")
        for key in stale:
            click.echo(f"  - s3://{bucket}/{key}")
        if not dry_run:
            # Batch delete in groups of 1000
            for i in range(0, len(stale), 1000):
                batch = stale[i : i + 1000]
                s3.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
                )
            click.echo(f"Deleted {len(stale)} stale chunk(s)")
        else:
            click.echo("Dry run: no deletions performed")
    else:
        click.echo("No stale chunks found.")

    # Final status
    if missing or ((old_chunks or index_stale) and not skip_freshness):
        raise click.ClickException(
            "Verification finished with issues (missing or stale files). See output above."
        )
    click.echo(
        "Verification complete: OK" + (" and recent" if not skip_freshness else "")
    )
