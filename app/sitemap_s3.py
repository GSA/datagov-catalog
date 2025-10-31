"""Helpers for sitemap-related S3 access."""

from __future__ import annotations

import os
from dataclasses import dataclass

from botocore.client import BaseClient
from botocore.session import get_session

_DEFAULT_PREFIX = "sitemap/"
_DEFAULT_INDEX_KEY = "sitemap.xml"


class SitemapS3ConfigError(RuntimeError):
    """Raised when required sitemap S3 configuration is missing."""


@dataclass(frozen=True)
class SitemapS3Config:
    bucket: str
    prefix: str = _DEFAULT_PREFIX
    index_key: str = _DEFAULT_INDEX_KEY


def get_sitemap_s3_config() -> SitemapS3Config:
    """Return the sitemap S3 configuration from environment variables."""

    bucket = os.getenv("SITEMAP_S3_BUCKET")
    if not bucket:
        raise SitemapS3ConfigError("SITEMAP_S3_BUCKET is required")
    prefix = os.getenv("SITEMAP_S3_PREFIX", _DEFAULT_PREFIX)
    index_key = os.getenv("SITEMAP_INDEX_KEY", _DEFAULT_INDEX_KEY)
    return SitemapS3Config(bucket=bucket, prefix=prefix, index_key=index_key)


def create_sitemap_s3_client() -> BaseClient:
    """Construct an S3 client configured for sitemap access."""

    region = os.getenv("SITEMAP_AWS_REGION")
    access_key = os.getenv("SITEMAP_AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("SITEMAP_AWS_SECRET_ACCESS_KEY")

    session = get_session()
    create_kwargs = {"region_name": region}
    if access_key and secret_key:
        create_kwargs.update(
            {
                "aws_access_key_id": access_key,
                "aws_secret_access_key": secret_key,
            }
        )
    return session.create_client("s3", **create_kwargs)
