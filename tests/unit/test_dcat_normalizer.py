import pytest

from app.dcat_normalizer import (
    normalize_conforms_to,
    normalize_described_by,
    normalize_landing_page,
    normalize_modified,
    normalize_rights,
    normalize_spatial,
    normalize_temporal,
)
from tests.fixtures import DCAT_3_0_DATASET_ID


class TestNormalizer:
    """Test DCAT-US 3.0 to 1.1 normalization functions."""

    def test_normalize_rights_array_to_string(self, interface_with_dataset):
        """Test DCAT 3.0 rights array → DCAT 1.1 string."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        rights = dataset.dcat.get("rights")

        normalized = normalize_rights(rights)

        assert isinstance(normalized, str)
        assert (
            normalized
            == "This data is in the public domain and available for unrestricted use."
        )

    def test_normalize_landing_page_object_to_string(self, interface_with_dataset):
        """Test DCAT 3.0 landingPage Document object → DCAT 1.1 URL string."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        landing_page = dataset.dcat.get("landingPage")

        normalized = normalize_landing_page(landing_page)

        assert isinstance(normalized, str)
        assert normalized == "https://example.gov/datasets/sample-dcat-3-0"

    def test_normalize_described_by_object_to_string(self, interface_with_dataset):
        """Test DCAT 3.0 describedBy Distribution object → DCAT 1.1 URL string."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        described_by = dataset.dcat.get("describedBy")

        normalized = normalize_described_by(described_by)

        assert isinstance(normalized, str)
        assert normalized == "https://example.gov/schemas/sample-schema.json"

    def test_normalize_temporal_array_to_string(self, interface_with_dataset):
        """Test DCAT 3.0 temporal PeriodOfTime array → DCAT 1.1 ISO 8601 string."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        temporal = dataset.dcat.get("temporal")

        normalized = normalize_temporal(temporal)

        assert isinstance(normalized, str)
        assert normalized == "2000-01-15T00:00:00Z/2023-12-31T00:00:00Z"

    def test_normalize_spatial_array_to_string(self, interface_with_dataset):
        """Test DCAT 3.0 spatial Location array → DCAT 1.1 string."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        spatial = dataset.dcat.get("spatial")

        normalized = normalize_spatial(spatial)

        assert isinstance(normalized, str)
        assert normalized == "United States"

    def test_normalize_conforms_to_array_to_string(self, interface_with_dataset):
        """Test DCAT 3.0 conformsTo Standard array → DCAT 1.1 URI string."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        conforms_to = dataset.dcat.get("conformsTo")

        normalized = normalize_conforms_to(conforms_to)

        assert isinstance(normalized, str)
        assert normalized == "https://www.iso.org/standard/53798.html"

    def test_normalize_modified_keeps_iso_date(self, interface_with_dataset):
        """Test DCAT 3.0 modified ISO date remains unchanged."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        modified = dataset.dcat.get("modified")

        normalized = normalize_modified(modified)

        assert isinstance(normalized, str)
        assert normalized == "2024-10-01"
