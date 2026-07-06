import pytest

from app.dcat_normalizer import normalize_rights
from tests.fixtures import DCAT_3_0_DATASET_ID


class TestNormalizer:
    """Test DCAT-US 3.0 to 1.1 normalization functions."""

    def test_normalize_rights_array_to_string(self, interface_with_dataset):
        """
        Test that DCAT 3.0 rights (array) is normalized to DCAT 1.1 format (string).

        DCAT 3.0: "rights": ["This data is in the public domain..."]
        DCAT 1.1: "rights": "This data is in the public domain..."
        """
        # Get the DCAT 3.0 test dataset
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        assert dataset is not None, "DCAT 3.0 test dataset should exist"

        # Verify it's in DCAT 3.0 format (array)
        rights = dataset.dcat.get("rights")
        assert isinstance(rights, list), "DCAT 3.0 rights should be an array"
        assert len(rights) > 0, "DCAT 3.0 rights array should not be empty"

        # Normalize to DCAT 1.1 format
        normalized_rights = normalize_rights(rights)

        # Assert it's now a string (DCAT 1.1 format)
        assert isinstance(normalized_rights, str), "Normalized rights should be a string"
        assert normalized_rights == rights[0], "Should return the first element of the array"
        assert normalized_rights == "This data is in the public domain and available for unrestricted use."
