import os
from datetime import date, datetime, timezone, timedelta
from typing import Iterable, Optional
from urllib.parse import urlparse
import posixpath
import xml.etree.ElementTree as ET

import click
from flask import Blueprint
from opensearchpy.exceptions import OpenSearchException

from .database import OpenSearchInterface
from .models import Dataset
from .sitemap_s3 import (
    SitemapS3ConfigError,
    create_sitemap_s3_client,
    get_sitemap_s3_config,
)

search = Blueprint("search", __name__)
sitemap = Blueprint("sitemap", __name__)

BASE_URL = os.getenv("SITEMAP_BASE_URL", "http://localhost:8080").rstrip("/")

@search.cli.command("sync")
@click.option("--start-page", help="Number of page to start on", default=1)
@click.option("--per_page", help="Number of datasets per page", default=100)
def sync_opensearch(start_page=1, per_page=100):
    """Sync the datasets to the OpenSearch system."""

    client = OpenSearchInterface.from_environment()

    # enpty the index and then refill it
    # THIS WILL CAUSE INCONSISTENT SEARCH RESULTS DURING THE PROCESS
    click.echo("Emptying dataset index...")
    client.delete_all_datasets()

    click.echo("Indexing...")

    # do our own pagination of the dataset query before calling into the
    # index_datasets method
    total_pages = Dataset.query.paginate(per_page=per_page).pages
    click.echo(f"Indexing {total_pages} pages of datasets...")
    # page numbers are 1-indexed
    for i in range(start_page, total_pages + 1):
        try:
            succeeded, failed = client.index_datasets(
                Dataset.query.paginate(page=i, per_page=per_page)
            )
        except OpenSearchException:
            # one more attempt after the exception
            # exceptions that this raises will propagate
            succeeded, failed = client.index_datasets(
                Dataset.query.paginate(page=i, per_page=per_page)
            )

        click.echo(f"Indexed page {i} with {succeeded} successes and {failed} errors.")


def register_commands(app):
    app.register_blueprint(search)
    app.register_blueprint(sitemap)


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
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">",
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
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">",
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
    click.echo(f"Total datasets: {total}; generating {total_chunks} chunk(s) of size {chunk_size}")

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
@click.option("--dry-run", is_flag=True, default=False, help="Show actions without deleting")
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
        if isinstance(index_last_modified, datetime) and index_last_modified < threshold:
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
            if key and key.endswith(".xml") and posixpath.basename(key).startswith("sitemap-"):
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
    click.echo("Verification complete: OK" + (" and recent" if not skip_freshness else ""))
