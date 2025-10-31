import click
from flask import Blueprint
from opensearchpy.exceptions import OpenSearchException

from .database import OpenSearchInterface
from .models import Dataset

search = Blueprint("search", __name__)


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
