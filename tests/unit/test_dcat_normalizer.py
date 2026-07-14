from app.dcat_normalizer import (
    normalize_access_rights,
    normalize_accrual_periodicity,
    normalize_conforms_to,
    normalize_described_by,
    normalize_distribution_license,
    normalize_issued,
    normalize_landing_page,
    normalize_language,
    normalize_modified,
    normalize_publisher_sub_org,
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

    def test_normalize_issued_keeps_iso_datetime(self, interface_with_dataset):
        """Test DCAT 3.0 issued ISO datetime remains unchanged."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        issued = dataset.dcat.get("issued")

        normalized = normalize_issued(issued)

        assert isinstance(normalized, str)
        assert normalized == "2020-01-15T00:00:00Z"

    def test_normalize_access_rights_maps_to_access_level(self, interface_with_dataset):
        """Test DCAT 3.0 accessRights maps to accessLevel if missing."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        access_rights = dataset.dcat.get("accessRights")
        access_level = dataset.dcat.get("accessLevel")

        normalized = normalize_access_rights(access_rights, access_level)

        assert normalized == "public"

    def test_normalize_language_iso_to_rfc(self, interface_with_dataset):
        """Test DCAT 3.0 language ISO 639-1 codes → DCAT 1.1 RFC 5646 tags."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        language = dataset.dcat.get("language")

        normalized = normalize_language(language)

        assert isinstance(normalized, list)
        assert normalized == ["en-US"]

    def test_normalize_accrual_periodicity_keeps_value(self, interface_with_dataset):
        """Test DCAT 3.0 accrualPeriodicity remains unchanged."""
        dataset = interface_with_dataset.get_dataset_by_id(DCAT_3_0_DATASET_ID)
        periodicity = dataset.dcat.get("accrualPeriodicity")

        normalized = normalize_accrual_periodicity(periodicity)

        assert normalized == "annually"

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
