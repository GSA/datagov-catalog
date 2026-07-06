import pytest

from app.dcat_opensearch import (
    collection_uri_from_dcat,
    collection_uri_from_hit,
    identifier_id,
    normalize_identifier,
    normalize_in_series,
    normalize_theme,
    theme_pref_labels,
)


class TestNormalizeIdentifier:
    def test_string_identifier(self):
        assert normalize_identifier({"identifier": "cftc-dc1"}) == {"@id": "cftc-dc1"}

    def test_object_identifier(self):
        dcat = {
            "identifier": {
                "@id": "https://example.gov/id",
                "notation": "DATASET-1",
            }
        }
        assert normalize_identifier(dcat) == {
            "@id": "https://example.gov/id",
            "notation": "DATASET-1",
        }

    def test_missing_identifier(self):
        assert normalize_identifier({}) is None


class TestNormalizeTheme:
    def test_string_theme(self):
        assert normalize_theme({"theme": "Geospatial"}) == [{"prefLabel": "Geospatial"}]

    def test_string_list_theme(self):
        assert normalize_theme({"theme": ["Health", "Education"]}) == [
            {"prefLabel": "Health"},
            {"prefLabel": "Education"},
        ]

    def test_concept_objects(self):
        dcat = {
            "theme": [
                {
                    "@id": "https://example.gov/concepts/geospatial",
                    "prefLabel": "Geospatial",
                    "altLabel": "GIS",
                }
            ]
        }
        assert normalize_theme(dcat) == [
            {
                "@id": "https://example.gov/concepts/geospatial",
                "prefLabel": "Geospatial",
                "altLabel": "GIS",
            }
        ]


class TestNormalizeInSeries:
    def test_legacy_is_part_of(self):
        assert normalize_in_series(
            {"isPartOf": "https://catalog.data.gov/dataset/my-collection"}
        ) == [{"@id": "https://catalog.data.gov/dataset/my-collection"}]

    def test_in_series_objects(self):
        dcat = {
            "inSeries": [
                {
                    "@id": "https://example.gov/series/annual",
                    "title": "Annual Series",
                }
            ]
        }
        assert normalize_in_series(dcat) == [
            {
                "@id": "https://example.gov/series/annual",
                "title": "Annual Series",
            }
        ]

    def test_in_series_takes_precedence_over_is_part_of(self):
        dcat = {
            "inSeries": [{"@id": "https://example.gov/series/new"}],
            "isPartOf": "https://example.gov/legacy",
        }
        assert normalize_in_series(dcat) == [{"@id": "https://example.gov/series/new"}]


class TestReadHelpers:
    def test_identifier_id_from_string(self):
        assert identifier_id("cftc-dc1") == "cftc-dc1"

    def test_identifier_id_from_object(self):
        assert identifier_id({"@id": "cftc-dc1", "notation": "X"}) == "cftc-dc1"

    def test_theme_pref_labels_from_mixed_shapes(self):
        assert theme_pref_labels({"theme": "Geospatial"}) == ["Geospatial"]
        assert theme_pref_labels({"theme": [{"prefLabel": "Climate Science"}]}) == [
            "Climate Science"
        ]

    def test_collection_uri_from_dcat_prefers_in_series(self):
        dcat = {
            "inSeries": [{"@id": "https://example.gov/series/1"}],
            "isPartOf": "https://example.gov/legacy",
        }
        assert collection_uri_from_dcat(dcat) == "https://example.gov/series/1"

    def test_collection_uri_from_hit_uses_top_level_in_series(self):
        hit = {
            "inSeries": [{"@id": "https://example.gov/series/1"}],
            "dcat": {"isPartOf": "https://example.gov/legacy"},
        }
        assert collection_uri_from_hit(hit) == "https://example.gov/series/1"

    @pytest.mark.parametrize("value", [None, "", {}, []])
    def test_empty_values_return_none_or_empty(self, value):
        if value in (None, "", {}):
            assert identifier_id(value) is None
        if value in (None, {}, []):
            assert theme_pref_labels(value) == []
