from datetime import date, datetime

import pytest

from app.filters import (
    format_dcat_date,
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

    def test_date_only_string_returns_date(self):
        result = parse_datetime("2026-05-01")
        assert type(result) is date
        assert result == date(2026, 5, 1)

    @pytest.mark.parametrize(
        "value",
        [
            "2026-05-01T00:00:00",
            "2026-05-01T00:00:00Z",
            "2026-05-01T00:00:00+00:00",
        ],
    )
    def test_datetime_strings_return_datetime(self, value):
        result = parse_datetime(value)
        assert type(result) is datetime
        assert (result.year, result.month, result.day) == (2026, 5, 1)


class TestFormatDcatDate:

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("2026-05-01", "May 01, 2026"),
            ("2026-05-01T14:48:00", "May 01, 2026 at 02:48 PM"),
            ("2026-05-01T14:48:00Z", "May 01, 2026 at 02:48 PM"),
            ("2026-05-01T14:48:00+00:00", "May 01, 2026 at 02:48 PM"),
            ("2026-05-01T00:00:00", "May 01, 2026 at 12:00 AM"),
        ],
    )
    def test_round_trip_via_parse_datetime(self, raw, expected):
        assert format_dcat_date(parse_datetime(raw)) == expected
