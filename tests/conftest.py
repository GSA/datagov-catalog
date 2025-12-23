from datetime import date, datetime
from unittest.mock import Mock

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
    Locations,
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
def interface_with_location(interface, fixture_data):
    for location_data in fixture_data["locations"]:
        interface.db.add(Locations(**location_data))
    interface.db.commit()
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


@pytest.fixture
def mock_organization():
    """Mock organization for dataset tests."""
    mock_org = Mock()
    mock_org.to_dict.return_value = {
        "id": "org-123",
        "name": "Test Org",
        "slug": "test-org",
    }
    return mock_org


@pytest.fixture
def mock_dataset_with_datetime(mock_organization):
    """Mock dataset with datetime object in DCAT."""
    mock_dataset = Mock()
    mock_dataset.id = "test-id-123"
    mock_dataset.slug = "test-dataset"
    mock_dataset.dcat = {
        "title": "Test Dataset",
        "description": "Test description",
        "modified": datetime(2023, 6, 22, 20, 25, 39, 652070),
        "keyword": ["health", "education"],
        "publisher": {"name": "Test Publisher"},
    }
    mock_dataset.popularity = 100
    mock_dataset.organization = mock_organization
    return mock_dataset


@pytest.fixture
def mock_dataset_with_date(mock_organization):
    """Mock dataset with date object in DCAT."""
    mock_dataset = Mock()
    mock_dataset.id = "test-id-456"
    mock_dataset.slug = "test-dataset-2"
    mock_dataset.dcat = {
        "title": "Test Dataset 2",
        "description": "Test description 2",
        "issued": date(2006, 5, 31),
        "keyword": [],
        "publisher": {"name": "Test Publisher"},
    }
    mock_dataset.popularity = 50
    mock_dataset.organization = mock_organization
    return mock_dataset


@pytest.fixture
def mock_dataset_with_string_dates(mock_organization):
    """Mock dataset with string dates in DCAT."""
    mock_dataset = Mock()
    mock_dataset.id = "test-id-789"
    mock_dataset.slug = "test-dataset-3"
    mock_dataset.dcat = {
        "title": "Test Dataset 3",
        "description": "Test description 3",
        "modified": "2023-06-22T20:25:39.652070",
        "issued": "2006-05-31",
        "keyword": [],
        "publisher": {},
    }
    mock_dataset.popularity = None
    mock_dataset.organization = mock_organization
    return mock_dataset


@pytest.fixture
def mock_dataset_with_spatial(mock_organization):
    """Mock dataset with spatial data and datetime in DCAT."""
    mock_dataset = Mock()
    mock_dataset.id = "test-id-spatial"
    mock_dataset.slug = "test-spatial-dataset"
    mock_dataset.dcat = {
        "title": "Spatial Dataset",
        "description": "Dataset with spatial info",
        "modified": datetime(2023, 1, 15, 10, 30, 0),
        "spatial": "United States",
        "keyword": ["geography", "maps"],
        "publisher": {},
    }
    mock_dataset.popularity = 200
    mock_dataset.organization = mock_organization
    return mock_dataset


@pytest.fixture
def mock_opensearch_client():
    """Mock OpenSearchInterface client for command testing."""
    client = Mock()
    client.INDEX_NAME = "datasets"
    client.client = Mock()
    client.client.indices = Mock()
    client.client.indices.delete = Mock()
    client.client.indices.get_mapping = Mock(
        return_value={
            "datasets": {
                "mappings": {
                    "properties": {"keyword": {"fields": {"raw": {"type": "keyword"}}}}
                }
            }
        }
    )
    client.delete_all_datasets = Mock()
    client._ensure_index = Mock()
    client._refresh = Mock()
    client.index_datasets = Mock(return_value=(100, 0))
    return client
