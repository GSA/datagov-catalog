import click
from flask import Blueprint

from .database import CatalogDBInterface, OpenSearchInterface
from .models import Dataset

search = Blueprint("search", __name__)


@search.cli.command("sync")
def sync_opensearch():
    """Sync the datasets to the OpenSearch system."""

    client = OpenSearchInterface.from_environment()
    interface = CatalogDBInterface()

    # enpty the index and then refill it
    # THIS WILL CAUSE SEARCH QUERIES TO FAIL DURING THE PROCESS
    click.echo("Emptying dataset index...")
    client.delete_all_datasets()
    click.echo("Indexing datasets...")
    succeeded, failed = client.index_datasets(interface.db.query(Dataset))

    click.echo(f"Indexed {succeeded} items.")
    click.echo(f"There were {failed} errors")


def register_commands(app):
    app.register_blueprint(search)
