"""Test-only helpers for OpenSearch index setup."""

from app.database import OpenSearchInterface


def recreate_opensearch_index(client: OpenSearchInterface) -> None:
    """Drop and recreate the index so tests pick up the latest mapping."""
    if client.client.indices.exists(index=client.INDEX_NAME):
        client.client.indices.delete(index=client.INDEX_NAME)
    body = {"mappings": client.MAPPINGS}
    if client.SETTINGS:
        body["settings"] = client.SETTINGS
    client.client.indices.create(index=client.INDEX_NAME, body=body)
