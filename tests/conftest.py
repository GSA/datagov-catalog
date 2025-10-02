import pytest

from sqlalchemy.orm import scoped_session, sessionmaker

from app import create_app
from app.database import CatalogDBInterface
from app.models import (
    Organization,
    HarvestSource,
    HarvestJob,
    HarvestRecord,
    Dataset,
    db,
)


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
def client(app):
    yield app.test_client()


@pytest.fixture
def db_client(dbapp):
    yield dbapp.test_client()


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
    interface.db.add(Organization(id="1", name="test org"))
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
            id="1", harvest_source_id="1", harvest_job_id="1", identifier="identifier"
        )
    )
    interface_with_harvest_job.db.commit()
    yield interface_with_harvest_job


@pytest.fixture
def interface_with_dataset(interface_with_harvest_record):

    interface_with_harvest_record.db.add(
        Dataset(
            slug="test",
            dcat={"title": "test", "description": "this is the test description"},
            harvest_record_id="1",
        )
    )
    interface_with_harvest_record.db.commit()

    yield interface_with_harvest_record
