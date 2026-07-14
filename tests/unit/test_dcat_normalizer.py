from app.dcat_normalizer import (
    normalize_access_rights,
    normalize_distribution_license,
    normalize_publisher_sub_org,
)
from tests.fixtures import DCAT_3_0_DATASET_ID


class TestNormalizer:
    """Test DCAT-US 3.0 to 1.1 normalization functions."""

    def test_normalize_access_rights_maps_to_access_level(self, interface_with_dataset):
        """Test DCAT 3.0 accessRights maps to accessLevel if missing."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        access_rights = dataset.dcat.get("accessRights")
        access_level = dataset.dcat.get("accessLevel")

        normalized = normalize_access_rights(access_rights, access_level)

        assert normalized == "public"

    def test_normalize_publisher_sub_org_array_to_object(self, interface_with_dataset):
        """Test DCAT 3.0 publisher.subOrganizationOf array → DCAT 1.1 object."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        publisher = dataset.dcat.get("publisher")

        normalized = normalize_publisher_sub_org(publisher)

        assert isinstance(normalized.get("subOrganizationOf"), dict)
        assert (
            normalized["subOrganizationOf"]["name"] == "Department of Sample Services"
        )

    def test_normalize_distribution_license_moves_to_dataset(
        self, interface_with_dataset
    ):
        """Test license moves from distribution → dataset level."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        dcat = dataset.dcat.copy()

        normalized = normalize_distribution_license(dcat)

        assert "license" in normalized
        assert (
            normalized["license"]
            == "https://creativecommons.org/publicdomain/zero/1.0/"
        )
