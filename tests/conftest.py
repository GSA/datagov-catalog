import pytest
from dotenv import load_dotenv
from opensearchpy import OpenSearchException
from sqlalchemy.orm import scoped_session, sessionmaker

from app import create_app
from app.database import CatalogDBInterface, OpenSearchInterface
from app.models import (
    Dataset,
    HarvestJob,
    HarvestRecord,
    HarvestSource,
    Organization,
    db,
)

from .fixtures import fixture_data

fixture_data = pytest.fixture(fixture_data)

load_dotenv()


@pytest.fixture(scope="session", autouse=True)
def app():
    """Flask app.

    Used by default and one for the whole test session"""
    app = create_app()
    yield app


@pytest.fixture(autouse=True)
def dbapp(app):
    with app.app_context():
        # clear the database completely
        db.drop_all()
        # Make the tables from the models schema
        db.create_all()
        yield app


@pytest.fixture
def db_client(dbapp):
    yield dbapp.test_client()


@pytest.fixture
def cli_runner(dbapp):
    yield dbapp.test_cli_runner()


@pytest.fixture
def session(dbapp):
    connection = db.engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(bind=connection, autoflush=True)
    session = scoped_session(SessionLocal)
    yield session

    session.remove()
    transaction.rollback()
    connection.close()


@pytest.fixture
def interface(session) -> CatalogDBInterface:
    interface = CatalogDBInterface(session=session)
    # best effort to clear the opensearch index
    try:
        interface.opensearch.delete_all_datasets()
    except OpenSearchException:
        pass
    yield interface


@pytest.fixture
def interface_with_organization(interface, fixture_data):
    for organization_data in fixture_data["organization"]:
        interface.db.add(Organization(**organization_data))
    interface.db.commit()
    yield interface


@pytest.fixture
def interface_with_harvest_source(interface_with_organization, fixture_data):
    interface_with_organization.db.add(HarvestSource(**fixture_data["harvest_source"]))
    interface_with_organization.db.commit()
    yield interface_with_organization


@pytest.fixture
def interface_with_harvest_job(interface_with_harvest_source, fixture_data):
    interface_with_harvest_source.db.add(HarvestJob(**fixture_data["harvest_job"]))
    interface_with_harvest_source.db.commit()
    yield interface_with_harvest_source


@pytest.fixture
def interface_with_harvest_record(interface_with_harvest_job, fixture_data):
    harvest_records = fixture_data["harvest_record"]
    if isinstance(harvest_records, dict):
        harvest_records = [harvest_records]
    for harvest_record in harvest_records:
        interface_with_harvest_job.db.add(HarvestRecord(**harvest_record))
    interface_with_harvest_job.db.commit()
    yield interface_with_harvest_job


@pytest.fixture
def interface_with_dataset(interface_with_harvest_record, fixture_data):
    # add generic dataset record
    for dataset_data in fixture_data["dataset"]:
        interface_with_harvest_record.db.add(Dataset(**dataset_data))
    interface_with_harvest_record.db.commit()
    interface_with_harvest_record.opensearch.index_datasets(
        interface_with_harvest_record.db.query(Dataset)
    )

    yield interface_with_harvest_record


@pytest.fixture
def opensearch_client():
    return OpenSearchInterface(test_host="localhost")


@pytest.fixture
def html_tags_within_text():
    return """<p>The Division of Drinking Water requires laboratories to 
    submit water quality data directly. The data is received, and published 
    twice monthly on the Division's water quality 
    <a href="https://www.waterboards.ca.gov/drinking_water/certlic/drinkingwater/EDTlibrary.html">
    portal</a>. The resource here now is just a data dictionary for the 
    laboratory analysis data available from that portal, and in the near 
    future we plan to add curated data resources that include laboratory
    water quality results.</p>"""
