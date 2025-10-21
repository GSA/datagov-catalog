import os

import click
from flask import Blueprint

from .database import CatalogDBInterface
from .models import Dataset
from .opensearch import OpenSearchInterface

search = Blueprint("search", __name__)


@search.cli.command("sync")
def sync_opensearch():
    """Sync the datasets to the OpenSearch system."""

    opensearch_host = os.getenv("OPENSEARCH_HOST")
    if opensearch_host.endswith("es.awamzonaws.com"):
        client = OpenSearchInterface(aws_host=opensearch_host)
    else:
        client = OpenSearchInterface(test_host=opensearch_host)

    interface = CatalogDBInterface()
    succeeded, failed = client.index_datasets(interface.db.query(Dataset))

    click.echo(f"Indexed {succeeded} items.")
    click.echo(f"There were {failed} errors")


def register_commands(app):
    app.register_blueprint(search)
