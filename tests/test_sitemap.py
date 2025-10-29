from datetime import datetime, timedelta, timezone

import pytest
from botocore.session import get_session as botocore_get_session
from moto import mock_aws


def _list_keys(client, bucket, prefix=""):
    params = {"Bucket": bucket}
    if prefix:
        params["Prefix"] = prefix
    resp = client.list_objects_v2(**params)
    return [item["Key"] for item in resp.get("Contents", [])]


@pytest.fixture()
def s3_client(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("SITEMAP_S3_BUCKET", "test-bucket")
        monkeypatch.setenv("SITEMAP_S3_PREFIX", "sitemap/")
        monkeypatch.setenv("SITEMAP_INDEX_KEY", "sitemap.xml")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

        session = botocore_get_session()
        client = session.create_client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="test-bucket")
        yield client


def test_sitemap_generate_uploads_files(app, interface_with_dataset, s3_client, monkeypatch):
    # Base URL for loc entries
    monkeypatch.setenv("SITEMAP_BASE_URL", "http://localhost:8080")
    # Ensure at least one dataset is visible to the CLI's default DB session
    from app.models import Dataset, db
    with app.app_context():
        db.session.add(
            Dataset(
                id="cli-ds",
                slug="cli-test",
                dcat={"title": "cli test"},
                harvest_record_id="hr1",
                harvest_source_id="hs1",
                organization_id="org1",
            )
        )
        db.session.commit()
    runner = app.test_cli_runner()
    result = runner.invoke(args=["sitemap", "generate"])
    assert result.exit_code == 0, result.output

    # One index and at least one chunk
    keys = set(_list_keys(s3_client, "test-bucket"))
    assert "sitemap.xml" in keys
    # Default prefix is sitemap/
    chunk_keys = [
        k for k in keys if k.startswith("sitemap/") and k.endswith(".xml") and k != "sitemap.xml"
    ]
    assert any(k.endswith("sitemap-0.xml") for k in chunk_keys)

    index_obj = s3_client.get_object(Bucket="test-bucket", Key="sitemap.xml")
    index_xml = index_obj["Body"].read().decode()
    assert "<sitemapindex" in index_xml
    assert "<loc>http://localhost:8080/sitemap/sitemap-0.xml</loc>" in index_xml

    # Spot-check chunk body
    chunk_key = next(k for k in chunk_keys if k.endswith("sitemap-0.xml"))
    chunk_obj = s3_client.get_object(Bucket="test-bucket", Key=chunk_key)
    chunk_xml = chunk_obj["Body"].read().decode()
    assert "<urlset" in chunk_xml
    assert "/dataset/" in chunk_xml


def test_sitemap_routes_fetch_from_s3(app, s3_client):
    # Prepare stored index and chunk
    s3_client.put_object(Bucket="test-bucket", Key="sitemap.xml", Body=b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
  <sitemap>
    <loc>http://localhost:8080/sitemap/sitemap-0.xml</loc>
    <lastmod>2025-01-01</lastmod>
  </sitemap>
</sitemapindex>""", ContentType="application/xml")
    s3_client.put_object(Bucket="test-bucket", Key="sitemap/sitemap-0.xml", Body=b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
  <url><loc>http://localhost:8080/dataset/test</loc></url>
</urlset>""", ContentType="application/xml")

    client = app.test_client()
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert b"<sitemapindex" in r.data

    r = client.get("/sitemap/sitemap-0.xml")
    assert r.status_code == 200
    assert b"<urlset" in r.data


def test_sitemap_verify_deletes_stale(app, s3_client):
    # Create index referencing only sitemap-0
    s3_client.put_object(Bucket="test-bucket", Key="sitemap.xml", Body=b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
  <sitemap><loc>http://localhost:8080/sitemap/sitemap-0.xml</loc></sitemap>
</sitemapindex>""", ContentType="application/xml")
    # Present two chunks; one is stale extra and should be deleted
    s3_client.put_object(Bucket="test-bucket", Key="sitemap/sitemap-0.xml", Body=b"ok", ContentType="application/xml")
    s3_client.put_object(Bucket="test-bucket", Key="sitemap/sitemap-99.xml", Body=b"stale", ContentType="application/xml")

    runner = app.test_cli_runner()
    # Use a generous freshness to avoid failing for timestamps
    result = runner.invoke(args=["sitemap", "verify", "--max-age-hours", "24"])
    assert result.exit_code == 0, result.output

    # The stale key should have been deleted
    remaining_keys = _list_keys(s3_client, "test-bucket", prefix="sitemap/")
    assert "sitemap/sitemap-99.xml" not in remaining_keys


def test_sitemap_verify_skip_freshness(app, s3_client):
    # Make index and chunk with old timestamps
    s3_client.put_object(Bucket="test-bucket", Key="sitemap.xml", Body=b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
  <sitemap><loc>http://localhost:8080/sitemap/sitemap-0.xml</loc></sitemap>
</sitemapindex>""", ContentType="application/xml")
    s3_client.put_object(Bucket="test-bucket", Key="sitemap/sitemap-0.xml", Body=b"ok", ContentType="application/xml")

    from moto.s3.models import s3_backends

    account_id = next(iter(s3_backends.keys()))
    backend = next(iter(s3_backends[account_id].values()))
    bucket = backend.buckets["test-bucket"]
    old_time = datetime.now(timezone.utc) - timedelta(hours=48)
    bucket.keys["sitemap.xml"].last_modified = old_time
    bucket.keys["sitemap/sitemap-0.xml"].last_modified = old_time

    runner = app.test_cli_runner()
    # Without skip should fail (due to staleness)
    result = runner.invoke(args=["sitemap", "verify"])  # default 1 hour
    assert result.exit_code != 0

    # With skip should pass
    result = runner.invoke(args=["sitemap", "verify", "--skip-freshness"])
    assert result.exit_code == 0, result.output
