from unittest.mock import Mock

import pytest
from opensearchpy.exceptions import ConnectionTimeout

import app.database.opensearch as opensearch_module
from app.database import OpenSearchInterface
from app.models import Dataset
from tests.helpers.opensearch import index_datasets, run_with_timeout_retry


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
        index_datasets(opensearch_client, dataset_iterator)
        # the test dataset has title "test"
        result_obj = opensearch_client.search("test")
        assert len(result_obj.results) > 0

    def test_index_and_search_other_fields(
        self, interface_with_dataset, opensearch_client
    ):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        index_datasets(opensearch_client, dataset_iterator)
        # One of the Americorps datasets has tnxs-meph in an identifier
        result_obj = opensearch_client.search("tnxs-meph")
        assert len(result_obj.results) > 0

    def test_search_spatial_geometry_intersects(
        self, interface_with_dataset, opensearch_client
    ):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        index_datasets(opensearch_client, dataset_iterator)
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
        index_datasets(opensearch_client, dataset_iterator)
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
        index_datasets(opensearch_client, dataset_iterator)
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

    def test_search_collection(self, interface_with_dataset, opensearch_client):
        dataset_iterator = interface_with_dataset.db.query(Dataset)
        index_datasets(opensearch_client, dataset_iterator)

        result_obj = opensearch_client.search(
            "", collection="https://subdomain.domain/parent/example.shp.iso.xml"
        )
        assert len(result_obj.results) == 2


# _geometry_centroid is slightly different between harvester and catalog.
# in catalog the function returns None for invalid points (e.g. out-of-bounds) compared to
# harvester which returns the original geometry. _geometry_centroid is used in spatial search
# so keeping some tests here
class TestGeometryCentroid:
    def test_geometry_centroid_skips_out_of_range_longitude(self):
        """
        A longitude outside -180-180 (e.g. 185.34) must be excluded from the
        centroid calculation to prevent OpenSearch geo_point parse failures.
        """
        geometry = {
            "type": "Point",
            "coordinates": [185.34570208999997, 45.0],
        }
        centroid = OpenSearchInterface._geometry_centroid(geometry)
        # The single point is invalid, so no valid points remain,
        # so it should return none
        assert centroid is None

    def test_geometry_centroid_skips_out_of_range_latitude(self):
        """
        A latitude outside -90-90 (e.g. -90.90) must be excluded from the
        centroid calculation to prevent OpenSearch geo_point parse failures.
        """
        geometry = {
            "type": "Point",
            "coordinates": [-74.0, -90.90776196883162],
        }
        centroid = OpenSearchInterface._geometry_centroid(geometry)
        assert centroid is None

    def test_geometry_centroid_uses_valid_points_when_some_are_out_of_range(self):
        """
        When a geometry contains a mix of valid and out-of-range coordinates, the
        centroid is computed from only the valid points rather than discarding
        the whole geometry.
        """
        geometry = {
            "type": "MultiPoint",
            "coordinates": [
                [10.0, 20.0],  # valid
                [185.0, 45.0],  # invalid lon
                [30.0, -91.0],  # invalid lat
                [50.0, 60.0],  # valid
            ],
        }
        centroid = OpenSearchInterface._geometry_centroid(geometry)
        assert centroid is not None
        assert centroid["lon"] == pytest.approx(30.0)  # mean of 10.0 and 50.0
        assert centroid["lat"] == pytest.approx(40.0)  # mean of 20.0 and 60.0


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

    def test_keyword_normalized_sub_field_exists(self):
        """
        keyword.normalized sub-field must be present for case-insensitive search.
        """
        keyword_fields = OpenSearchInterface.MAPPINGS["properties"]["keyword"]["fields"]

        assert "normalized" in keyword_fields
        assert keyword_fields["normalized"]["type"] == "keyword"
        assert keyword_fields["normalized"]["normalizer"] == (
            OpenSearchInterface.KEYWORD_NORMALIZER
        )

    def test_lowercase_normalizer_defined_in_settings(self):
        """
        The lowercase_normalizer must be declared in SETTINGS so OpenSearch
        can apply it when doing index.
        """
        normalizers = OpenSearchInterface.SETTINGS.get("analysis", {}).get(
            "normalizer", {}
        )

        assert OpenSearchInterface.KEYWORD_NORMALIZER in normalizers
        normalizer_cfg = normalizers[OpenSearchInterface.KEYWORD_NORMALIZER]
        assert normalizer_cfg["type"] == "custom"
        assert "lowercase" in normalizer_cfg["filter"]

    def test_spatial_centroid_mapping(self):
        """Test that spatial centroid field is mapped as geo_point."""
        mappings = OpenSearchInterface.MAPPINGS
        assert mappings["properties"]["spatial_centroid"]["type"] == "geo_point"


class TestCaseInsensitiveKeywords:
    """
    Tests for case-insensitive keyword filtering and aggregation.
    """

    def _recreate_index(self, client: OpenSearchInterface) -> None:
        """Drop and recreate the index to pick up the latest mapping."""
        if client.client.indices.exists(index=client.INDEX_NAME):
            client.client.indices.delete(index=client.INDEX_NAME)
        body = {"mappings": client.MAPPINGS, "settings": client.SETTINGS}
        client.client.indices.create(index=client.INDEX_NAME, body=body)

    def _make_mock_dataset(
        self,
        doc_id: str,
        slug: str,
        keywords: list[str],
        mock_organization: Mock,
    ) -> Mock:
        """Return a minimal mock Dataset with the given keywords."""
        dataset = Mock()
        dataset.id = doc_id
        dataset.slug = slug
        dataset.last_harvested_date = Mock()
        dataset.last_harvested_date.isoformat.return_value = "2024-01-01"
        dataset.translated_spatial = None
        dataset.harvest_record_id = "harvest-rec-id"
        dataset.harvest_record = None
        dataset.popularity = 0
        dataset.organization = mock_organization
        dataset.dcat = {
            "title": f"Dataset {slug}",
            "description": "Test dataset for keyword case-insensitivity",
            "keyword": keywords,
            "publisher": {"name": "Test Agency"},
        }
        return dataset

    def test_keyword_filter_is_case_insensitive(
        self, dbapp, opensearch_client, mock_organization
    ):
        """
        Searching by lowercase keyword should match a dataset indexed with
        the same keyword in Title Case, and vice versa.
        """
        self._recreate_index(opensearch_client)

        with dbapp.app_context():
            dbapp.config["SERVER_NAME"] = "0.0.0.0:8080"
            dbapp.config["PREFERRED_URL_SCHEME"] = "http"

            # Index one dataset whose keyword is stored as "Environment" (Title Case)
            dataset = self._make_mock_dataset(
                doc_id="kw-case-test-1",
                slug="kw-case-dataset-1",
                keywords=["Environment", "Climate"],
                mock_organization=mock_organization,
            )

            index_datasets(opensearch_client, [dataset])

        # Filtering with the lowercase form must still find the document.
        result_lower = opensearch_client.search("", keywords=["environment"])
        assert len(result_lower.results) == 1

        # Filtering with the original Title Case form must also work.
        result_title = opensearch_client.search("", keywords=["Environment"])
        assert len(result_title.results) == 1

        # An unrelated keyword must return 0.
        result_none = opensearch_client.search("", keywords=["unrelated"])
        assert len(result_none.results) == 0

    def test_keyword_filter_case_insensitive_mixed_case(
        self, dbapp, opensearch_client, mock_organization
    ):
        """
        Mixed-case filter values must still resolve to the correct
        document regardless of how the keyword was stored.
        """
        self._recreate_index(opensearch_client)

        with dbapp.app_context():
            dbapp.config["SERVER_NAME"] = "0.0.0.0:8080"
            dbapp.config["PREFERRED_URL_SCHEME"] = "http"

            dataset = self._make_mock_dataset(
                doc_id="kw-case-test-mixed",
                slug="kw-case-dataset-mixed",
                keywords=["environment"],
                mock_organization=mock_organization,
            )
            index_datasets(opensearch_client, [dataset])

        # "ENVIRONMENT", "Environment", and "eNvIrOnMeNt" should all match.
        for variant in ("ENVIRONMENT", "Environment", "eNvIrOnMeNt"):
            result = opensearch_client.search("", keywords=[variant])
            assert len(result.results) == 1

    def test_get_unique_keywords_combines_case_variants(
        self, dbapp, opensearch_client, mock_organization
    ):
        """
        Indexing 'environment' and 'Environment' across two datasets should
        produce a single aggregation bucket with a combined doc_count of 2.
        """
        self._recreate_index(opensearch_client)

        with dbapp.app_context():
            dbapp.config["SERVER_NAME"] = "0.0.0.0:8080"
            dbapp.config["PREFERRED_URL_SCHEME"] = "http"

            dataset_lower = self._make_mock_dataset(
                doc_id="kw-agg-test-1",
                slug="kw-agg-dataset-lower",
                keywords=["environment"],
                mock_organization=mock_organization,
            )
            dataset_title = self._make_mock_dataset(
                doc_id="kw-agg-test-2",
                slug="kw-agg-dataset-title",
                keywords=["Environment"],
                mock_organization=mock_organization,
            )

            index_datasets(opensearch_client, [dataset_lower, dataset_title])

        keywords = opensearch_client.get_unique_keywords()

        # Both variants must collapse into one bucket.
        env_buckets = [k for k in keywords if k["keyword"] == "environment"]
        assert len(env_buckets) == 1
        assert env_buckets[0]["count"] == 2

    def test_get_unique_keywords_search_filters_by_substring(
        self, dbapp, opensearch_client, mock_organization
    ):
        """
        Passing search="earth science" should return only keyword buckets whose
        normalized value contains that substring, ordered by doc count descending.
        Unrelated keywords must not appear in the results.
        """
        self._recreate_index(opensearch_client)

        with dbapp.app_context():
            dbapp.config["SERVER_NAME"] = "0.0.0.0:8080"
            dbapp.config["PREFERRED_URL_SCHEME"] = "http"

            datasets = [
                self._make_mock_dataset(
                    doc_id="kw-search-1",
                    slug="kw-search-1",
                    keywords=["earth"],
                    mock_organization=mock_organization,
                ),
                self._make_mock_dataset(
                    doc_id="kw-search-2",
                    slug="kw-search-2",
                    keywords=["earth science"],
                    mock_organization=mock_organization,
                ),
                self._make_mock_dataset(
                    doc_id="kw-search-3",
                    slug="kw-search-3",
                    keywords=["earth science > trees"],
                    mock_organization=mock_organization,
                ),
                self._make_mock_dataset(
                    doc_id="kw-search-4",
                    slug="kw-search-4",
                    keywords=["ocean"],
                    mock_organization=mock_organization,
                ),
            ]
            index_datasets(opensearch_client, datasets)

        keywords = opensearch_client.get_unique_keywords(search="earth science")
        keyword_values = [item["keyword"] for item in keywords]

        assert "earth science" in keyword_values
        assert "earth science > trees" in keyword_values
        # "earth" does not contain the substring "earth science"
        assert "earth" not in keyword_values
        # Completely unrelated keywords must be excluded
        assert "ocean" not in keyword_values


def test_count_datasets_with_ispartof_passes_filtered_count_query():
    """OpenSearch count returns the number of docs matching the supplied query."""
    client = OpenSearchInterface.__new__(OpenSearchInterface)
    client.INDEX_NAME = "datasets"
    client.client = Mock()
    client.client.count.return_value = {"count": 7}

    count = client.count_datasets_with_ispartof()

    assert count == 7
    client.client.count.assert_called_once_with(
        index=client.INDEX_NAME,
        body={
            "query": {
                "nested": {
                    "path": "dcat",
                    "query": {"exists": {"field": "dcat.isPartOf"}},
                }
            }
        },
    )


def test_relevance_sort_uses_popularity_tie_breaker():
    client = OpenSearchInterface.__new__(OpenSearchInterface)
    sort_clause = client._build_sort_clause("relevance")
    assert sort_clause == [
        {"_score": {"order": "desc"}},
        {"popularity": {"order": "desc", "missing": "_last"}},
        {"_id": {"order": "desc"}},
    ]


def test_distance_sort_uses_geo_distance():
    client = OpenSearchInterface.__new__(OpenSearchInterface)
    sort_clause = client._build_sort_clause(
        "distance", sort_point={"lat": 40.0, "lon": -75.0}
    )
    assert sort_clause[0]["_geo_distance"]["spatial_centroid"] == {
        "lat": 40.0,
        "lon": -75.0,
    }
    assert sort_clause[0]["_geo_distance"]["order"] == "asc"


def test_last_harvested_date_sort_uses_latest_first():
    client = OpenSearchInterface.__new__(OpenSearchInterface)
    sort_clause = client._build_sort_clause("last_harvested_date")
    assert sort_clause == [
        {"last_harvested_date": {"order": "desc", "missing": "_last"}},
        {"_score": {"order": "desc"}},
        {"popularity": {"order": "desc", "missing": "_last"}},
        {"_id": {"order": "desc"}},
    ]


def test_run_with_timeout_retry_eventual_success(monkeypatch):
    monkeypatch.setattr(opensearch_module.time, "sleep", lambda _: None)

    attempts = {"count": 0}

    def _action():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ConnectionTimeout("TIMEOUT")
        return "done"

    result = run_with_timeout_retry(
        _action,
        timeout_retries=3,
        timeout_backoff_base=2.0,
    )

    assert result == "done"
    assert attempts["count"] == 3


def test_run_with_timeout_retry_exhausted(monkeypatch):
    monkeypatch.setattr(opensearch_module.time, "sleep", lambda _: None)

    def _action():
        raise ConnectionTimeout("TIMEOUT")

    with pytest.raises(ConnectionTimeout):
        run_with_timeout_retry(
            _action,
            timeout_retries=2,
            timeout_backoff_base=2.0,
        )
