from app.api_schemas import Dataset


def test_dataset_schema_preserves_scalar_identifier():
    result = Dataset().dump({"identifier": "https://example.gov/datasets/one"})

    assert result["identifier"] == "https://example.gov/datasets/one"


def test_dataset_schema_preserves_theme_list_values():
    result = Dataset().dump(
        {
            "theme": [
                {
                    "@id": "https://example.gov/concepts/climate-science",
                    "prefLabel": "Climate Science",
                    "altLabel": ["Climatology"],
                    "notation": ["CLIM-SCI"],
                }
            ]
        }
    )

    assert result["theme"] == [
        {
            "@id": "https://example.gov/concepts/climate-science",
            "prefLabel": "Climate Science",
            "altLabel": ["Climatology"],
            "notation": ["CLIM-SCI"],
        }
    ]
