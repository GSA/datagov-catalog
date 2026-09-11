from app.search.mappings import MAPPINGS


def test_has_download_field_mapping():
    assert MAPPINGS["properties"]["has_download"]["type"] == "boolean"


def test_parent_identifier_field_mapping():
    assert MAPPINGS["properties"]["parent_identifier"] == {"type": "keyword"}
