import json

import pytest


@pytest.mark.skip(
    reason="Browser tests require manual data seeding - run seed_compact_metadata.py first"
)
def test_json_raw_metadata_is_formatted(page):
    page.goto("/harvest_record/b306a1c1-f26f-4e55-9142-4643d084b2b0/raw")

    body_text = page.locator("body").inner_text()

    assert "\n" in body_text
    assert "  " in body_text

    parsed = json.loads(body_text)
    assert parsed["identifier"] == "EPA-AQI-2024"


@pytest.mark.skip(
    reason="Browser tests require manual data seeding - run seed_compact_metadata.py first"
)
def test_xml_raw_metadata_is_formatted(page):
    page.goto("/harvest_record/a4958853-b2e8-4a93-9767-d45fa269fff6/raw")

    content = page.content()

    assert "\n" in content
    assert "  " in content or "\t" in content
    assert "USGS-EARTHQUAKE-CATALOG-2024" in content
