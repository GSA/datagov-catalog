import pytest

from app.dcat_normalizer import normalize_landing_page, normalize_rights
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
