from unittest.mock import Mock

import pytest

from app.search.documents import DatasetDocument


@pytest.fixture
def sample_dataset(mock_organization):
    dataset = Mock()
    dataset.id = "dataset-1"
    dataset.slug = "dataset-1"
    dataset.dcat = {
        "title": "Dataset Title",
        "description": "Dataset description",
        "publisher": {"name": "Publisher"},
        "keyword": ["kw-1"],
        "theme": ["theme-1"],
        "identifier": "id-1",
        "distribution": [
            {"title": "CSV download"},
            {"title": "API endpoint"},
        ],
    }
    dataset.last_harvested_date = None
    dataset.translated_spatial = None
    dataset.organization = mock_organization
    dataset.popularity = 7
    dataset.harvest_record_id = None
    dataset.harvest_record = None
    return dataset


def test_dataset_to_document_has_download_when_download_url_present(sample_dataset):
    sample_dataset.dcat["distribution"].append(
        {"title": "Data file", "downloadURL": "https://example.gov/data.csv"}
    )

    dataset_doc = DatasetDocument(sample_dataset)
    document = dataset_doc.dataset_to_document()

    assert document["has_download"] is True


def test_dataset_to_document_has_download_false_for_access_url_only(sample_dataset):
    sample_dataset.dcat["distribution"] = [
        {"title": "API endpoint", "accessURL": "https://example.gov/api"}
    ]

    dataset_doc = DatasetDocument(sample_dataset)
    document = dataset_doc.dataset_to_document()

    assert document["has_download"] is False


@pytest.mark.parametrize("distribution", [None, [], "not-a-list"])
def test_dataset_to_document_has_download_false_when_distribution_missing(
    sample_dataset, distribution
):
    sample_dataset.dcat["distribution"] = distribution

    dataset_doc = DatasetDocument(sample_dataset)
    document = dataset_doc.dataset_to_document()

    assert document["has_download"] is False


def test_dataset_to_document_has_download_false_for_blank_download_url(
    sample_dataset,
):
    sample_dataset.dcat["distribution"] = [{"title": "Blank", "downloadURL": "   "}]

    dataset_doc = DatasetDocument(sample_dataset)
    document = dataset_doc.dataset_to_document()

    assert document["has_download"] is False
