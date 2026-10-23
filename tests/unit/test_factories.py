from collections import Counter

import pytest

from app.filters import resolve_resource_format
from app.models import Dataset, HarvestRecord, HarvestSource, Organization
from tests.factories import TOPIC_PROFILES, generated_test_data
from tests.fixtures import fixture_data


@pytest.fixture
def source_fixture_data():
    return fixture_data(include_filter_demos=True)


@pytest.fixture
def generated_fixture_data(source_fixture_data):
    return generated_test_data(source_fixture_data)


def _snapshot(fixture_data):
    return {
        collection: [instance.to_dict() for instance in instances]
        for collection, instances in fixture_data.items()
    }


def test_generated_test_data_is_reproducible():
    first = generated_test_data(fixture_data(include_filter_demos=True))
    second = generated_test_data(fixture_data(include_filter_demos=True))

    assert _snapshot(first) == _snapshot(second)


def test_generated_test_data_preserves_fixture_structure_and_adds_topics(
    generated_fixture_data,
    source_fixture_data,
):
    expected_topic_count = len(TOPIC_PROFILES) * 2

    assert len(generated_fixture_data["organizations"]) == len(
        source_fixture_data["organization"]
    )

    assert len(generated_fixture_data["harvest_sources"]) == (
        1 + len(source_fixture_data.get("extra_harvest_source", []))
    )

    assert len(generated_fixture_data["datasets"]) == (
        len(source_fixture_data["dataset"]) + expected_topic_count
    )

    assert len(generated_fixture_data["harvest_records"]) == (
        len(source_fixture_data["harvest_record"]) + expected_topic_count
    )


def test_generated_datasets_have_unique_ids_and_slugs(generated_fixture_data):
    datasets = generated_fixture_data["datasets"]

    assert len({dataset.id for dataset in datasets}) == len(datasets)
    assert len({dataset.slug for dataset in datasets}) == len(datasets)


def test_topic_datasets_cover_each_subject_twice(generated_fixture_data):
    topic_datasets = [
        dataset
        for dataset in generated_fixture_data["datasets"]
        if dataset.slug.startswith("generated-topic-")
    ]

    assert len(topic_datasets) == len(TOPIC_PROFILES) * 2

    topic_themes = {dataset.dcat["theme"][0] for dataset in topic_datasets}
    assert len(topic_themes) == len(TOPIC_PROFILES)

    for _, title, _, _ in TOPIC_PROFILES:
        assert (
            sum(dataset.dcat["title"].startswith(title) for dataset in topic_datasets)
            == 2
        )


def test_topic_datasets_are_distributed_across_all_harvest_sources(
    generated_fixture_data,
):
    topic_datasets = [
        dataset
        for dataset in generated_fixture_data["datasets"]
        if dataset.slug.startswith("generated-topic-")
    ]
    sources_by_id = {
        source.id: source for source in generated_fixture_data["harvest_sources"]
    }

    assert {dataset.harvest_source_id for dataset in topic_datasets} == set(
        sources_by_id
    )

    assert all(
        sources_by_id[dataset.harvest_source_id].organization_id
        == dataset.organization_id
        for dataset in topic_datasets
    )


def test_generated_datasets_cover_access_metadata_forms(generated_fixture_data):
    access_values = Counter(
        dataset.dcat.get("accessLevel", dataset.dcat.get("accessRights"))
        for dataset in generated_fixture_data["datasets"]
    )

    assert {
        "public",
        "non-public",
        "restricted public",
        "restricted",
    } <= set(access_values)

    assert access_values[None] == 0

    assert all(
        dataset.dcat.get("accessLevel") or dataset.dcat.get("accessRights")
        for dataset in generated_fixture_data["datasets"]
    )

    assert all(
        value is not None
        for dataset in generated_fixture_data["datasets"]
        for field in ("accessLevel", "accessRights")
        if field in dataset.dcat
        for value in (dataset.dcat[field],)
    )


def test_known_dcat_3_fixture_retains_access_level_and_access_rights(
    generated_fixture_data,
):
    datasets_by_slug = {
        dataset.slug: dataset for dataset in generated_fixture_data["datasets"]
    }

    dcat = datasets_by_slug["test-dcat-3-0"].dcat

    assert dcat["accessLevel"] == "public"
    assert dcat["accessRights"] == "public"


def test_non_geospatial_demo_dataset_remains_non_geospatial(generated_fixture_data):
    datasets_by_slug = {
        dataset.slug: dataset for dataset in generated_fixture_data["datasets"]
    }

    dataset = datasets_by_slug["michigan-research-grants"]

    assert dataset.translated_spatial is None
    assert "spatial" not in dataset.dcat


def test_enriched_datasets_and_harvest_records_stay_synchronized(
    generated_fixture_data,
):
    datasets_by_record_id = {
        dataset.harvest_record_id: dataset
        for dataset in generated_fixture_data["datasets"]
    }

    for record in generated_fixture_data["harvest_records"]:
        dataset = datasets_by_record_id.get(record.id)
        if dataset is None:
            continue

        assert record.harvest_source_id == dataset.harvest_source_id
        assert record.source_transform == dataset.dcat


def test_generated_datasets_cover_resource_edge_cases(generated_fixture_data):
    datasets = generated_fixture_data["datasets"]

    distribution_sizes = {len(dataset.dcat["distribution"]) for dataset in datasets}

    assert 0 in distribution_sizes
    assert max(distribution_sizes) > 6

    resource_formats = {
        resolve_resource_format(resource)
        for dataset in datasets
        for resource in dataset.dcat["distribution"]
    }

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


def test_generated_datasets_cover_metadata_shape_variants(generated_fixture_data):
    datasets = generated_fixture_data["datasets"]

    assert any(isinstance(dataset.dcat.get("temporal"), dict) for dataset in datasets)
    assert any(
        isinstance(dataset.dcat.get("contactPoint"), list) for dataset in datasets
    )
    assert any(isinstance(dataset.dcat.get("publisher"), str) for dataset in datasets)


def test_generated_datasets_cover_spatial_metadata_variants(generated_fixture_data):
    datasets = generated_fixture_data["datasets"]

    assert any(isinstance(dataset.dcat.get("spatial"), str) for dataset in datasets)
    assert any(isinstance(dataset.dcat.get("spatial"), dict) for dataset in datasets)
    assert any("spatial" not in dataset.dcat for dataset in datasets)


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
