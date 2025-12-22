from datetime import date, datetime

import pytest
from opensearchpy.exceptions import ConnectionTimeout

import app.database.opensearch as opensearch_module
from app.database import OpenSearchInterface
from app.models import Dataset


class TestOpenSearch:

    def test_bad_host_arguments(self):
        with pytest.raises(ValueError):
            # no hostnames
            OpenSearchInterface()

        with pytest.raises(ValueError):
            # both hostnames
            OpenSearchInterface(test_host="not-empty", aws_host="also-not-empty")

    def test_index_and_search_datasets(self, interface_with_dataset, opensearch_client):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        opensearch_client.index_datasets(dataset_iterator)
        # the test dataset has title "test"
        result_obj = opensearch_client.search("test")
        assert len(result_obj.results) > 0

    def test_index_and_search_other_fields(
        self, interface_with_dataset, opensearch_client
    ):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        opensearch_client.index_datasets(dataset_iterator)
        # One of the Americorps datasets has tnxs-meph in an identifier
        result_obj = opensearch_client.search("tnxs-meph")
        assert len(result_obj.results) > 0

    def test_search_spatial_geometry_intersects(
        self, interface_with_dataset, opensearch_client
    ):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        opensearch_client.index_datasets(dataset_iterator)
        # This point is inside the polygon of the test dataset
        result_obj = opensearch_client.search(
            "",
            spatial_geometry={"type": "point", "coordinates": [-75, 40]},
            spatial_within=False,
        )
        assert len(result_obj.results) > 0

    def test_search_spatial_geometry_within(
        self, interface_with_dataset, opensearch_client
    ):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        opensearch_client.index_datasets(dataset_iterator)
        # This polygon contains the whole test dataset (and planet)
        result_obj = opensearch_client.search(
            "",
            spatial_geometry={
                "type": "polygon",
                "coordinates": [
                    [[-180, -90], [180, -90], [180, 90], [-180, 90], [-180, -90]]
                ],
            },
            spatial_within=True,
        )
        assert len(result_obj.results) > 0

    def test_search_spatial_geometry_intersects_not_within(
        self, interface_with_dataset, opensearch_client
    ):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        opensearch_client.index_datasets(dataset_iterator)
        # This polygon intersects the test dataset but doesn't contain it
        polygon = {
            "type": "polygon",
            "coordinates": [[[-85, 30], [-85, 40], [-75, 40], [-75, 30], [-85, 30]]],
        }
        result_obj = opensearch_client.search(
            "", spatial_geometry=polygon, spatial_within=True
        )
        assert len(result_obj.results) == 0

        result_obj = opensearch_client.search(
            "", spatial_geometry=polygon, spatial_within=False
        )
        assert len(result_obj.results) > 0


class TestDcatDateNormalization:
    """Test suite for _normalize_dcat_dates method."""

    def test_normalize_datetime_modified_field(self):
        """Test that datetime objects in modified field are converted to ISO strings."""
        dcat = {
            "title": "Test Dataset",
            "modified": datetime(2023, 6, 22, 20, 25, 39, 652070),
            "description": "Test description",
        }

        result = OpenSearchInterface._normalize_dcat_dates(dcat)

        assert isinstance(result["modified"], str)
        assert result["modified"] == "2023-06-22T20:25:39.652070"
        assert result["title"] == "Test Dataset"
        assert result["description"] == "Test description"

    def test_normalize_date_modified_field(self):
        """Test that date objects in modified field are converted to ISO strings."""
        dcat = {
            "title": "Test Dataset",
            "modified": date(2023, 6, 22),
            "description": "Test description",
        }

        result = OpenSearchInterface._normalize_dcat_dates(dcat)

        assert isinstance(result["modified"], str)
        assert result["modified"] == "2023-06-22"

    def test_normalize_datetime_issued_field(self):
        """Test that datetime objects in issued field are converted to ISO strings."""
        dcat = {
            "title": "Test Dataset",
            "issued": datetime(2006, 5, 31, 0, 0, 0),
            "description": "Test description",
        }

        result = OpenSearchInterface._normalize_dcat_dates(dcat)

        assert isinstance(result["issued"], str)
        assert result["issued"] == "2006-05-31T00:00:00"

    def test_normalize_multiple_date_fields(self):
        """Test that multiple date fields are all normalized."""
        dcat = {
            "title": "Test Dataset",
            "modified": datetime(2023, 6, 22, 20, 25, 39),
            "issued": date(2006, 5, 31),
            "temporal": "2004/2005",
            "description": "Test description",
        }

        result = OpenSearchInterface._normalize_dcat_dates(dcat)

        assert isinstance(result["modified"], str)
        assert result["modified"] == "2023-06-22T20:25:39"
        assert isinstance(result["issued"], str)
        assert result["issued"] == "2006-05-31"
        assert result["temporal"] == "2004/2005"  # Already string

    def test_normalize_leaves_string_dates_unchanged(self):
        """Test that date fields that are already strings are not modified."""
        dcat = {
            "title": "Test Dataset",
            "modified": "2023-06-22T20:25:39.652070",
            "issued": "2006-05-31",
            "description": "Test description",
        }

        result = OpenSearchInterface._normalize_dcat_dates(dcat)

        assert result["modified"] == "2023-06-22T20:25:39.652070"
        assert result["issued"] == "2006-05-31"

    def test_normalize_with_missing_date_fields(self):
        """Test that missing date fields don't cause errors."""
        dcat = {
            "title": "Test Dataset",
            "description": "Test description",
            "keyword": ["health", "education"],
        }

        result = OpenSearchInterface._normalize_dcat_dates(dcat)

        assert "modified" not in result
        assert "issued" not in result
        assert result["title"] == "Test Dataset"
        assert result["keyword"] == ["health", "education"]

    def test_normalize_with_none_date_fields(self):
        """Test that None values in date fields are preserved."""
        dcat = {
            "title": "Test Dataset",
            "modified": None,
            "issued": None,
            "description": "Test description",
        }

        result = OpenSearchInterface._normalize_dcat_dates(dcat)

        assert result["modified"] is None
        assert result["issued"] is None

    def test_normalize_with_integer_date_field(self):
        """Test that non-standard types (like integers) are converted to strings."""
        dcat = {
            "title": "Test Dataset",
            "modified": 20230622,  # Non-standard format
            "description": "Test description",
        }

        result = OpenSearchInterface._normalize_dcat_dates(dcat)

        assert isinstance(result["modified"], str)
        assert result["modified"] == "20230622"

    def test_normalize_does_not_mutate_original(self):
        """Test that the original dcat dict is not modified."""
        modified_datetime = datetime(2023, 6, 22, 20, 25, 39)
        dcat = {
            "title": "Test Dataset",
            "modified": modified_datetime,
            "description": "Test description",
        }

        result = OpenSearchInterface._normalize_dcat_dates(dcat)

        # Original should still have datetime object
        assert isinstance(dcat["modified"], datetime)
        assert dcat["modified"] is modified_datetime
        # Result should have string
        assert isinstance(result["modified"], str)

    def test_normalize_preserves_nested_structures(self):
        """Test that nested structures in DCAT are preserved."""
        dcat = {
            "title": "Test Dataset",
            "modified": datetime(2023, 6, 22, 20, 25, 39),
            "publisher": {
                "name": "Department of Education",
                "subOrganizationOf": {"name": "U.S. Government"},
            },
            "distribution": [
                {"title": "Data File", "downloadURL": "https://example.com/data.csv"}
            ],
        }

        result = OpenSearchInterface._normalize_dcat_dates(dcat)

        assert isinstance(result["modified"], str)
        assert result["publisher"]["name"] == "Department of Education"
        assert result["publisher"]["subOrganizationOf"]["name"] == "U.S. Government"
        assert len(result["distribution"]) == 1
        assert result["distribution"][0]["title"] == "Data File"


class TestDatasetToDocument:
    """Test suite for dataset_to_document with date normalization."""

    def test_dataset_to_document_normalizes_modified_datetime(
        self, opensearch_client, mock_dataset_with_datetime, mock_organization
    ):
        """Test that dataset_to_document normalizes datetime in modified field."""
        # Convert to document
        document = opensearch_client.dataset_to_document(mock_dataset_with_datetime)

        # Verify modified is a string
        assert isinstance(document["dcat"]["modified"], str)
        assert document["dcat"]["modified"] == "2023-06-22T20:25:39.652070"
        assert document["title"] == "Test Dataset"
        assert document["slug"] == "test-dataset"

    def test_dataset_to_document_normalizes_issued_date(
        self, opensearch_client, mock_dataset_with_date, mock_organization
    ):
        """Test that dataset_to_document normalizes date in issued field."""
        document = opensearch_client.dataset_to_document(mock_dataset_with_date)

        assert isinstance(document["dcat"]["issued"], str)
        assert document["dcat"]["issued"] == "2006-05-31"

    def test_dataset_to_document_preserves_string_dates(
        self, opensearch_client, mock_dataset_with_string_dates, mock_organization
    ):
        """Test that string dates in DCAT are preserved as-is."""
        document = opensearch_client.dataset_to_document(mock_dataset_with_string_dates)

        assert document["dcat"]["modified"] == "2023-06-22T20:25:39.652070"
        assert document["dcat"]["issued"] == "2006-05-31"

    def test_dataset_to_document_with_spatial_data(
        self, opensearch_client, mock_dataset_with_spatial, mock_organization
    ):
        """Test dataset_to_document with spatial data and date normalization."""
        document = opensearch_client.dataset_to_document(mock_dataset_with_spatial)

        assert document["has_spatial"] is True
        assert isinstance(document["dcat"]["modified"], str)
        assert document["dcat"]["modified"] == "2023-01-15T10:30:00"

    def test_dataset_to_document_does_not_modify_original_dcat(
        self, opensearch_client, mock_dataset_with_datetime, mock_organization
    ):
        """Test that the original dataset.dcat is not mutated."""
        modified_datetime = mock_dataset_with_datetime.dcat["modified"]

        # Convert to document
        document = opensearch_client.dataset_to_document(mock_dataset_with_datetime)

        # Original dcat should still have datetime object
        assert isinstance(mock_dataset_with_datetime.dcat["modified"], datetime)
        assert mock_dataset_with_datetime.dcat["modified"] is modified_datetime

        # Document should have string
        assert isinstance(document["dcat"]["modified"], str)


class TestOpenSearchMappings:
    """Test suite for OpenSearch mappings."""

    def test_dcat_modified_field_mapping(self):
        """Test that DCAT modified field is mapped as keyword type."""
        mappings = OpenSearchInterface.MAPPINGS

        assert "dcat" in mappings["properties"]
        assert mappings["properties"]["dcat"]["type"] == "nested"
        assert "properties" in mappings["properties"]["dcat"]

        dcat_properties = mappings["properties"]["dcat"]["properties"]
        assert "modified" in dcat_properties
        assert dcat_properties["modified"]["type"] == "keyword"

    def test_dcat_issued_field_mapping(self):
        """Test that DCAT issued field is mapped as keyword type."""
        mappings = OpenSearchInterface.MAPPINGS
        dcat_properties = mappings["properties"]["dcat"]["properties"]

        assert "issued" in dcat_properties
        assert dcat_properties["issued"]["type"] == "keyword"

    def test_other_mappings_unchanged(self):
        """Test that other field mappings are preserved."""
        mappings = OpenSearchInterface.MAPPINGS

        # Verify other fields are still present
        assert mappings["properties"]["title"]["type"] == "text"
        assert mappings["properties"]["slug"]["type"] == "keyword"
        assert mappings["properties"]["keyword"]["type"] == "text"
        assert mappings["properties"]["keyword"]["fields"]["raw"]["type"] == "keyword"
        assert mappings["properties"]["organization"]["type"] == "nested"


def test_relevance_sort_uses_popularity_tie_breaker():
    client = OpenSearchInterface.__new__(OpenSearchInterface)
    sort_clause = client._build_sort_clause("relevance")
    assert sort_clause == [
        {"_score": {"order": "desc"}},
        {"popularity": {"order": "desc", "missing": "_last"}},
        {"_id": {"order": "desc"}},
    ]


def test_run_with_timeout_retry_eventual_success(monkeypatch):
    interface = OpenSearchInterface.__new__(OpenSearchInterface)
    monkeypatch.setattr(opensearch_module.time, "sleep", lambda _: None)

    attempts = {"count": 0}

    def _action():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ConnectionTimeout("TIMEOUT")
        return "done"

    result = interface._run_with_timeout_retry(
        _action,
        action_name="test action",
        timeout_retries=3,
        timeout_backoff_base=2.0,
    )

    assert result == "done"
    assert attempts["count"] == 3


def test_run_with_timeout_retry_exhausted(monkeypatch):
    interface = OpenSearchInterface.__new__(OpenSearchInterface)
    monkeypatch.setattr(opensearch_module.time, "sleep", lambda _: None)

    def _action():
        raise ConnectionTimeout("TIMEOUT")

    with pytest.raises(ConnectionTimeout):
        interface._run_with_timeout_retry(
            _action,
            action_name="test action",
            timeout_retries=2,
            timeout_backoff_base=2.0,
        )
