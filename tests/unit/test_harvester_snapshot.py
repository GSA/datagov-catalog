"""Exercise catalog's reads against the real harvester snapshot.

See tests/data/harvester_snapshot/README.md. Unlike most of the suite, which builds
precise synthetic rows via fixtures.py, these tests confirm catalog's own code works
against actual harvester-shaped rows and OpenSearch documents.
"""

from unittest.mock import patch


def test_snapshot_organization_is_queryable(interface_with_harvester_snapshot):
    org = interface_with_harvester_snapshot.get_organization_by_slug("fixture-org")
    assert org is not None
    assert org.name == "Test Org"
    assert org.organization_type == "Federal Government"


def test_snapshot_harvest_record_is_queryable(interface_with_harvester_snapshot):
    record = interface_with_harvester_snapshot.get_harvest_record(
        "09f073b3-00e3-4147-ba69-a5d0fd7ce021"
    )
    assert record is not None
    assert record.identifier == "test_identifier-9"
    assert record.status == "success"


def test_snapshot_dataset_search_returns_results(
    db_client, interface_with_harvester_snapshot
):
    with patch("app.routes.interface", interface_with_harvester_snapshot):
        response = db_client.get("/search", query_string={"q": "Fixture"})

    assert response.status_code == 200
    results = response.get_json()["results"]
    assert len(results) == 2
    slugs = {result["slug"] for result in results}
    assert slugs == {"fixture-dataset-1", "fixture-dataset-2"}


def test_snapshot_dataset_detail_renders(db_client, interface_with_harvester_snapshot):
    with patch("app.routes.interface", interface_with_harvester_snapshot):
        response = db_client.get("/dataset/fixture-dataset-1")

    assert response.status_code == 200
    assert b"Fixture Dataset 1" in response.data
