import pytest

from app.filters import (
    parse_datetime,
    remove_html_tags,
    simplify_resource_type,
)


def test_remove_html_tags(html_tags_within_text):
    assert (
        remove_html_tags(html_tags_within_text)
        == "The Division of Drinking Water requires laboratories to \n    submit water quality data directly. The data is received, and published \n    twice monthly on the Division's water quality \n    \n    portal. The resource here now is just a data dictionary for the \n    laboratory analysis data available from that portal, and in the near \n    future we plan to add curated data resources that include laboratory\n    water quality results."
    )


def test_lt_or_gt_not_removed():
    assert remove_html_tags("in x < 0, but also y > 0") == "in x < 0, but also y > 0"


class TestSimplifyResourceType:
    """
    Tests for `simplify_resource_type`. We should either get a supported
    str based from the regex or a None value.
    """

    def test_mime_type_xml(self):
        assert simplify_resource_type("application/xml") == "xml"

    def test_bare_extension(self):
        assert simplify_resource_type("PDF") == "PDF"

    def test_unused_string_returns_none(self):
        assert simplify_resource_type("shp") is None

    def test_empty_string_returns_none(self):
        assert simplify_resource_type("") is None

    def test_none_returns_none(self):
        assert simplify_resource_type(None) is None


class TestParseDatetime:
    """
    Tests for the `parse_datetime` filter.
    """

    @pytest.mark.parametrize(
        "value",
        [
            "2026-05-01",
            "2026-05-01T00:00:00",
            "2026-05-01T00:00:00Z",
            "2026-05-01T00:00:00+00:00",
        ],
    )
    def test_common_dcat_formats_parse_to_may_01(self, value):
        result = parse_datetime(value)
        assert result is not None
        assert (result.year, result.month, result.day) == (2026, 5, 1)
