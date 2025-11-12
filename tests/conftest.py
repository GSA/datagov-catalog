import csv
import json
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import func
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

HARVEST_RECORD_ID = "e8b2ef79-8dbe-4d2e-9fe8-dc6766c0b5ab"
DATASET_ID = "e8b2ef79-8dbe-4d2e-9fe8-dc6766c0b5ab"
TEST_DIR = Path(__file__).parent

load_dotenv()


# helpers functions
def read_csv(file_path) -> list:
    output = []
    with open(file_path) as f:
        csv_reader = csv.reader(f)
        for row in csv_reader:
            output.append(row)
    return output


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
    return CatalogDBInterface(session=session)


@pytest.fixture
def interface_with_organization(interface):
    interface.db.add(
        Organization(
            id="1",
            name="test org",
            slug="test-org",
            organization_type="Federal Government",
        )
    )
    interface.db.commit()
    yield interface


@pytest.fixture
def interface_with_harvest_source(interface_with_organization):
    interface_with_organization.db.add(
        HarvestSource(
            id="1",
            name="test-source",
            organization_id="1",
            url="not-a-url",
            frequency="manual",
            schema_type="dcatus1.1: non-federal",
            source_type="document",
            notification_frequency="always",
        )
    )
    interface_with_organization.db.commit()
    yield interface_with_organization


@pytest.fixture
def interface_with_harvest_job(interface_with_harvest_source):
    interface_with_harvest_source.db.add(
        HarvestJob(id="1", harvest_source_id="1", status="complete")
    )
    interface_with_harvest_source.db.commit()
    yield interface_with_harvest_source


@pytest.fixture
def interface_with_harvest_record(interface_with_harvest_job):
    interface_with_harvest_job.db.add(
        HarvestRecord(
            id=HARVEST_RECORD_ID,
            harvest_source_id="1",
            harvest_job_id="1",
            identifier="identifier",
            source_raw='{"title": "test dataset"}',
            source_transform={
                "title": "test dataset",
                "extras": {"foo": "bar"},
            },
        )
    )
    interface_with_harvest_job.db.commit()
    yield interface_with_harvest_job


@pytest.fixture
def interface_with_dataset(interface_with_harvest_record):
    # add generic dataset record
    interface_with_harvest_record.db.add(
        Dataset(
            id=DATASET_ID,
            slug="test",
            dcat={
                "title": "test",
                "description": "this is the test description",
                "distribution": [
                    {
                        "title": "Test CSV",
                        "description": "Sample CSV resource",
                        "format": "CSV",
                        "downloadURL": "https://example.com/test.csv",
                        "mediaType": "text/csv",
                    }
                ],
                "keywords": ["health", "education", "employment", "test"],
            },
            harvest_record_id=HARVEST_RECORD_ID,
            harvest_source_id="1",
            organization_id="1",
            search_vector=func.to_tsvector("english", "test description"),
        )
    )

    # add additional dataset records
    datasets = read_csv(TEST_DIR / "data" / "americorps_datasets.csv")
    fields = datasets[0]

    for row in datasets[1:]:
        row[-2] = func.to_tsvector("english", row[1])  # search_vector
        row[1] = json.loads(row[1])  # dcat
        row[5] = int(row[5])  # popularity
        interface_with_harvest_record.db.add(Dataset(**dict(zip(fields, row))))

    interface_with_harvest_record.db.commit()

    yield interface_with_harvest_record


@pytest.fixture
def opensearch_client():
    return OpenSearchInterface(test_host="localhost")
