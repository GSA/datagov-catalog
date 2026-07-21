import os
import posixpath
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional
from urllib.parse import urlparse

import click
from datagov_data_access.search.client import OpenSearchClient
from datagov_data_access.search.reader import OpenSearchReader
from datagov_data_access.search.writer import OpenSearchWriter
from flask import Blueprint

from .database import CatalogDBInterface
from .models import (
    Dataset,
    HarvestJob,
    HarvestRecord,
    HarvestSource,
    Locations,
    Organization,
    db,
)
from .sitemap_s3 import (
    SitemapS3ConfigError,
    create_sitemap_s3_client,
    get_sitemap_s3_config,
)

search = Blueprint("search", __name__)
sitemap = Blueprint("sitemap", __name__)
testdata = Blueprint("testdata", __name__)

BASE_URL = os.getenv("SITEMAP_BASE_URL", "http://localhost:8080").rstrip("/")


def _normalize_last_harvested(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(cleaned)
        except ValueError:
            return cleaned
    else:
        return str(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    dt = dt.replace(microsecond=(dt.microsecond // 1000) * 1000)
    return dt.isoformat(timespec="milliseconds")


def _normalize_mapping_for_comparison(value):
    """Normalize mapping defaults omitted by OpenSearch responses."""
    if isinstance(value, dict):
        normalized = {
            key: _normalize_mapping_for_comparison(item) for key, item in value.items()
        }
        if normalized.get("search_analyzer") is not None and normalized.get(
            "search_analyzer"
        ) == normalized.get("analyzer"):
            normalized.pop("search_analyzer")
        return normalized

    if isinstance(value, list):
        return [_normalize_mapping_for_comparison(item) for item in value]

    return value


def register_commands(app):
    app.register_blueprint(search)
    app.register_blueprint(sitemap)
    app.register_blueprint(testdata)


@testdata.cli.command("load_test_data")
@click.option(
    "--clear",
    is_flag=True,
    help="Drop and recreate all database tables before loading",
    default=False,
)
def load_test_data(clear):
    """
    Load test fixture data into the database.

    Use --clear flag to drop all tables and recreate them before loading data.
    """
    from tests.fixtures import fixture_data

    fixture = fixture_data(include_filter_demos=True)
    interface = CatalogDBInterface(db.session)

    if clear:
        click.echo("Dropping all database tables...")
        try:
            db.drop_all()
            click.echo("All tables dropped.")
        except Exception as e:
            click.echo(f"Warning: Could not drop tables: {e}")

        click.echo("Creating all database tables...")
        try:
            db.create_all()
            click.echo("All tables created.")
        except Exception as e:
            click.echo(f"Error creating tables: {e}")
            raise

    click.echo("Loading test data...")
    try:
        for organization_data in fixture["organization"]:
            interface.db.add(Organization(**organization_data))
        interface.db.add(HarvestSource(**fixture["harvest_source"]))
        for extra_source in fixture.get("extra_harvest_source", []):
            interface.db.add(HarvestSource(**extra_source))
        interface.db.add(HarvestJob(**fixture["harvest_job"]))
        for record in fixture["harvest_record"]:
            interface.db.add(HarvestRecord(**record))
        for data in fixture["dataset"]:
            interface.db.add(Dataset(**data))
        for location in fixture["locations"]:
            interface.db.add(Locations(**location))
        interface.db.commit()
        click.echo("Test data loaded successfully.")
    except Exception as e:
        interface.db.rollback()
        click.echo(f"Error loading test data: {e}")
        raise


@search.cli.command("compare")
@click.option(
    "--sample-size",
    default=10,
    show_default=True,
    help="How many example IDs to print for each discrepancy type.",
)
@click.option(
    "--update",
    is_flag=True,
    help=(
        "Automatically index missing/updated datasets and delete extra docs "
        "from OpenSearch."
    ),
)
@click.option(
    "--force-update",
    is_flag=True,
    help="Re-index all datasets from DB regardless of last_harvested_date.",
)
def compare_opensearch(sample_size: int, update: bool, force_update: bool):
    """Report and optionally repair DB/OpenSearch dataset discrepancies."""
    os_client = OpenSearchClient.from_environment()
    os_writer = OpenSearchWriter(os_client)
    os_reader = OpenSearchReader(os_client)

    db_interface = CatalogDBInterface(db.session)
    reharvest = {}

    click.echo("Collecting dataset IDs from DB...")
    db_rows = db_interface.db.query(Dataset.id, Dataset.last_harvested_date).all()
    db_last_harvested = {
        dataset_id: _normalize_last_harvested(last_harvested)
        for dataset_id, last_harvested in db_rows
    }
    db_ids = set(db_last_harvested)
    click.echo(f"Database datasets: {len(db_ids)}")

    click.echo("Collecting document IDs from OpenSearch...")
    os_docs = {}

    for hit in os_reader.scan_index(
        index_name=os_client.INDEX_NAME,
        size=200,
        source=False,
        stored_fields=[],
        docvalue_fields=["last_harvested_date"],
    ):
        fields = hit.get("fields", {})
        last_harvested = None
        if fields.get("last_harvested_date"):
            last_harvested = fields["last_harvested_date"][0]
        elif hit.get("_source"):
            last_harvested = hit["_source"].get("last_harvested_date")
        os_docs[hit["_id"]] = _normalize_last_harvested(last_harvested)

    os_ids = set(os_docs)
    click.echo(f"OpenSearch documents: {len(os_ids)}")

    missing = sorted(db_ids - os_ids)
    extra = sorted(os_ids - db_ids)
    shared_ids = sorted(db_ids & os_ids)
    updated_details = [
        (dataset_id, db_last_harvested.get(dataset_id), os_docs.get(dataset_id))
        for dataset_id in shared_ids
        if db_last_harvested.get(dataset_id) != os_docs.get(dataset_id)
    ]
    updated_ids = [dataset_id for dataset_id, _, _ in updated_details]

    click.echo(f"Missing in OpenSearch (should be indexed): {len(missing)}")
    click.echo(
        "Example missing IDs: "
        + (", ".join(missing[:sample_size]) if missing else "none")
    )
    click.echo(f"Extra in OpenSearch (should be deleted): {len(extra)}")
    click.echo(
        "Example extra IDs: " + (", ".join(extra[:sample_size]) if extra else "none")
    )
    click.echo(
        f"Updated in OpenSearch (last_harvested_date differs): {len(updated_details)}"
    )
    if updated_details:
        sample_entries = [
            f"{dataset_id} (DB: {db_value or 'None'}, OS: {os_value or 'None'})"
            for dataset_id, db_value, os_value in updated_details[:sample_size]
        ]
        click.echo("Example updated IDs: " + "; ".join(sample_entries))
    else:
        click.echo("Example updated IDs: none")

    if force_update:
        update = True
    if not update:
        return

    click.echo("\nUpdating discrepancies...")
    force_reindex_ids = sorted(db_ids) if force_update else []
    if force_reindex_ids:
        os_writer.index_dataset_batches(
            force_reindex_ids,
            f"Force re-indexing {len(force_reindex_ids)} datasets...",
            db_interface,
            sample_size=sample_size,
            log_all_errors=True,
        )
    else:
        if missing:
            os_writer.index_dataset_batches(
                missing,
                f"Indexing {len(missing)} missing datasets...",
                db_interface,
                sample_size=sample_size,
                log_all_errors=True,
            )
        if updated_ids:
            os_writer.index_dataset_batches(
                updated_ids,
                f"Re-indexing {len(updated_ids)} updated datasets...",
                db_interface,
                sample_size=sample_size,
                log_all_errors=True,
            )
    # print the harvest sources with datasets that couldn't sync with opensearch
    click.echo("Harvest sources not synced with opensearch...")
    for harvest_source_id, harvest_source_name in reharvest.items():
        click.echo(f"{harvest_source_id} {harvest_source_name}")

    if extra:
        click.echo(f"Deleting {len(extra)} extra documents from OpenSearch…")
        deleted = 0
        batch_size = 1000
        total_batches = (len(extra) + batch_size - 1) // batch_size
        for batch_number, batch_ids in enumerate(
            (extra[i : i + batch_size] for i in range(0, len(extra), batch_size)),
            start=1,
        ):
            click.echo(
                f"  Batch {batch_number}/{total_batches}: deleting {len(batch_ids)} document(s)…"
            )
            for doc_id in batch_ids:
                try:
                    os_client.client.delete(index=os_client.INDEX_NAME, id=doc_id)
                    deleted += 1
                except Exception as exc:  # pragma: no cover - best-effort cleanup
                    click.echo(f"    Failed to delete document {doc_id}: {exc}")

        click.echo(f"Deleted {deleted} documents from OpenSearch.")

    if missing or extra or updated_ids or force_reindex_ids:
        click.echo("Refreshing OpenSearch index…")
        os_writer._refresh()
        click.echo("Done.")
    else:
        click.echo("Nothing to update; datasets and index are already in sync.")


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
    default=lambda: int(os.getenv("SITEMAP_CHUNK_SIZE", "5000")),
    help="URLs per sitemap file (default 5000)",
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

    dbi = CatalogDBInterface(db.session)

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
            dbi.db.query(Dataset.slug, Dataset.last_harvested_date)
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
