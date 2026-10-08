from collections import Counter

from app.filters import resolve_resource_format
from app.models import Dataset, HarvestRecord, HarvestSource, Organization
from tests.factories import generated_test_data
from tests.fixtures import fixture_data


def _snapshot(generated):
    return {
        collection: [instance.to_dict() for instance in instances]
        for collection, instances in generated.items()
    }


def test_generated_test_data_enriches_the_existing_pool_reproducibly():
    first = generated_test_data(fixture_data(include_filter_demos=True))
    second = generated_test_data(fixture_data(include_filter_demos=True))

    assert _snapshot(first) == _snapshot(second)
    assert len(first["organizations"]) == 15
    assert len(first["harvest_sources"]) == 9
    assert len(first["harvest_records"]) == 110
    assert len(first["datasets"]) == 110
    assert len({dataset.id for dataset in first["datasets"]}) == 110
    assert len({dataset.slug for dataset in first["datasets"]}) == 110
    assert (
        sum(
            dataset.slug.startswith("generated-topic-") for dataset in first["datasets"]
        )
        == 24
    )
    assert (
        sum(
            dataset.dcat["title"].startswith("Transit Ridership")
            for dataset in first["datasets"]
        )
        == 2
    )
    assert (
        len(
            {
                dataset.dcat["theme"][0]
                for dataset in first["datasets"]
                if dataset.slug.startswith("generated-topic-")
            }
        )
        == 12
    )

    access_levels = Counter(
        dataset.dcat.get("accessLevel", dataset.dcat.get("accessRights"))
        for dataset in first["datasets"]
    )
    assert {"public", "non-public", "restricted public", "restricted"} <= set(
        access_levels
    )
    assert access_levels[None] > 0

    datasets_by_record = {
        dataset.harvest_record_id: dataset for dataset in first["datasets"]
    }
    assert all(
        record.harvest_source_id == datasets_by_record[record.id].harvest_source_id
        and record.source_transform == datasets_by_record[record.id].dcat
        for record in first["harvest_records"]
        if record.id in datasets_by_record
    )

    distribution_sizes = {
        len(dataset.dcat["distribution"]) for dataset in first["datasets"]
    }
    resource_formats = {
        resolve_resource_format(resource)
        for dataset in first["datasets"]
        for resource in dataset.dcat["distribution"]
    }
    assert 0 in distribution_sizes
    assert max(distribution_sizes) > 6
    assert {
        "CSV",
        "application/json",
        "geojson",
        "XLSX",
        "PDF",
        "KML",
        "application/vnd.unknown-format",
        "application/x-netcdf",
        "zip",
    } <= resource_formats
    assert any(
        isinstance(dataset.dcat.get("temporal"), dict) for dataset in first["datasets"]
    )
    assert any(
        isinstance(dataset.dcat.get("contactPoint"), list)
        for dataset in first["datasets"]
    )
    assert any(
        isinstance(dataset.dcat.get("publisher"), str) for dataset in first["datasets"]
    )


def test_factoryboy_pytest_fixtures_build_models(
    organization,
    harvest_source,
    harvest_record,
    dataset,
):
    assert isinstance(organization, Organization)
    assert isinstance(harvest_source, HarvestSource)
    assert isinstance(harvest_record, HarvestRecord)
    assert isinstance(dataset, Dataset)
