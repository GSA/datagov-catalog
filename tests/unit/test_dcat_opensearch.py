import pytest

from app.dcat_opensearch import (
    collection_uri_from_dcat,
    collection_uri_from_hit,
    identifier_id,
    normalize_identifier,
    normalize_theme,
    theme_pref_labels,
)


class TestNormalizeIdentifier:
    def test_string_identifier(self):
        assert normalize_identifier({"identifier": "cftc-dc1"}) == "cftc-dc1"

    def test_object_identifier(self):
        dcat = {
            "identifier": {
                "@id": "https://example.gov/id",
                "notation": "DATASET-1",
            }
        }
        assert normalize_identifier(dcat) == "https://example.gov/id"

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

    def test_collection_uri_from_dcat_uses_is_part_of(self):
        dcat = {
            "isPartOf": "https://example.gov/legacy",
        }
        assert collection_uri_from_dcat(dcat) == "https://example.gov/legacy"

    def test_collection_uri_from_dcat_reads_object_is_part_of(self):
        dcat = {
            "isPartOf": {
                "@id": "https://example.gov/series/object",
                "@type": "DatasetSeries",
            },
        }
        assert collection_uri_from_dcat(dcat) == "https://example.gov/series/object"

    def test_collection_uri_from_dcat_falls_back_to_in_series(self):
        dcat = {
            "inSeries": [
                {
                    "@id": "https://example.gov/series/annual-climate",
                    "@type": "DatasetSeries",
                }
            ],
        }
        assert (
            collection_uri_from_dcat(dcat)
            == "https://example.gov/series/annual-climate"
        )

    def test_collection_uri_from_dcat_prefers_is_part_of_over_in_series(self):
        dcat = {
            "isPartOf": "https://example.gov/legacy",
            "inSeries": [{"@id": "https://example.gov/series/dcat3"}],
        }
        assert collection_uri_from_dcat(dcat) == "https://example.gov/legacy"

    def test_collection_uri_from_hit_uses_dcat_blob(self):
        hit = {
            "dcat": {"isPartOf": "https://example.gov/legacy"},
        }
        assert collection_uri_from_hit(hit) == "https://example.gov/legacy"

    @pytest.mark.parametrize("value", [None, "", {}, []])
    def test_empty_values_return_none_or_empty(self, value):
        if value in (None, "", {}):
            assert identifier_id(value) is None
        if value in (None, {}, []):
            assert theme_pref_labels(value) == []
