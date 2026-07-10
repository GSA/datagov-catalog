import pytest

from app.dcat_opensearch import (
    collection_uri_from_dcat,
    collection_uri_from_hit,
    distribution_titles,
    identifier_id,
    normalize_identifier,
    normalize_keywords,
    normalize_publisher_name,
    normalize_text,
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

    def test_single_concept_object(self):
        dcat = {
            "theme": {
                "@id": "https://example.gov/concepts/geospatial",
                "prefLabel": "Geospatial",
            }
        }
        assert normalize_theme(dcat) == [
            {
                "@id": "https://example.gov/concepts/geospatial",
                "prefLabel": "Geospatial",
            }
        ]

    def test_concept_objects_keep_list_values(self):
        dcat = {
            "theme": [
                {
                    "@id": "https://example.gov/concepts/climate-science",
                    "prefLabel": "Climate Science",
                    "altLabel": ["Climatology", "Climate"],
                    "notation": ["CLIM-SCI"],
                    "definition": "The study of climate.",
                    "inScheme": {"title": "Science Domains"},
                }
            ]
        }
        assert normalize_theme(dcat) == [
            {
                "@id": "https://example.gov/concepts/climate-science",
                "prefLabel": "Climate Science",
                "altLabel": ["Climatology", "Climate"],
                "notation": ["CLIM-SCI"],
                "definition": "The study of climate.",
            }
        ]


class TestSearchFieldNormalizers:
    def test_normalize_text_rejects_non_strings(self):
        assert normalize_text("Dataset title") == "Dataset title"
        assert normalize_text({"value": "Dataset title"}) == ""

    def test_normalize_keywords_wraps_single_string(self):
        assert normalize_keywords("climate") == ["climate"]

    def test_normalize_publisher_name_falls_back_to_preflabel(self):
        assert (
            normalize_publisher_name({"prefLabel": "United States Census Bureau"})
            == "United States Census Bureau"
        )

    def test_distribution_titles_extracts_non_empty_titles(self):
        assert distribution_titles([{"title": "CSV"}, {"title": ""}, "skip"]) == ["CSV"]


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
        assert theme_pref_labels({"prefLabel": "Geospatial"}) == ["Geospatial"]

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
