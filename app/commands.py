import os
from typing import Iterable, Optional

import click
from flask import Blueprint

from .database import CatalogDBInterface
from .models import Dataset
from .opensearch import OpenSearchInterface
from botocore.session import get_session

search = Blueprint("search", __name__)
sitemap = Blueprint("sitemap", __name__)


@search.cli.command("sync")
def sync_opensearch():
    """Sync the datasets to the OpenSearch system."""

    opensearch_host = os.getenv("OPENSEARCH_HOST")
    if opensearch_host.endswith("es.amazonaws.com"):
        client = OpenSearchInterface(aws_host=opensearch_host)
    else:
        client = OpenSearchInterface(test_host=opensearch_host)

    interface = CatalogDBInterface()
    succeeded, failed = client.index_datasets(interface.db.query(Dataset))

    click.echo(f"Indexed {succeeded} items.")
    click.echo(f"There were {failed} errors")


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
        base_url = os.getenv("SITEMAP_BASE_URL", "http://localhost:8080").rstrip("/")
        loc = f"{base_url}/dataset/{ds.slug}"
        lastmod = _sitemap_lastmod(ds)
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines)


def _build_sitemap_index_xml(total_chunks: int) -> str:
    base_url = os.getenv("SITEMAP_BASE_URL", "http://localhost:8080").rstrip("/")
    lines = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">",
    ]
    for idx in range(total_chunks):
        loc = f"{base_url}/sitemap/sitemap-{idx}.xml"
        lines.append("  <sitemap>")
        lines.append(f"    <loc>{loc}</loc>")
        lines.append("  </sitemap>")
    lines.append("</sitemapindex>")
    return "\n".join(lines)


def _s3_client_and_config():
    bucket = os.getenv("SITEMAP_S3_BUCKET")
    if not bucket:
        raise click.ClickException("SITEMAP_S3_BUCKET is required")
    prefix = os.getenv("SITEMAP_S3_PREFIX", "sitemap/")
    index_key = os.getenv("SITEMAP_INDEX_KEY", "sitemap.xml")
    region = os.getenv("AWS_DEFAULT_REGION")
    session = get_session()
    s3 = session.create_client("s3", region_name=region)
    return s3, bucket, prefix, index_key


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
