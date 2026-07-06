"""Populate OpenSearch for catalog browser and accessibility tests."""

import os

from app import create_app
from app.models import Dataset
from tests.vendor.opensearch_index import OpenSearchInterface


def main():
    os.environ.setdefault("CATALOG_BASE_URL", "http://0.0.0.0:8080")
    app = create_app()
    with app.app_context():
        writer = OpenSearchInterface.from_environment()
        writer.client.delete_by_query(
            index=writer.INDEX_NAME,
            body={"query": {"match_all": {}}},
            request_timeout=120,
        )
        writer.index_datasets(Dataset.query)


if __name__ == "__main__":
    main()
