from app.filter_helpers import (
    geography_active_summary,
    organization_active_summary,
    publisher_active_summary,
    selection_summary,
    truncate_summary,
)


def test_selection_summary_single():
    assert selection_summary(["health"]) == "health"


def test_selection_summary_multiple():
    assert selection_summary(["health", "food"]) == "2 selected"


def test_selection_summary_empty():
    assert selection_summary(None) is None
    assert selection_summary([]) is None


def test_selection_summary_truncates_long_single_value():
    assert selection_summary(["A" * 60]) == f"{'A' * 47}…"


def test_selection_summary_does_not_truncate_count_label():
    assert selection_summary(["a", "b", "c"]) == "3 selected"


def test_organization_active_summary_from_object():
    class Org:
        name = "City of Portland"

    assert organization_active_summary(Org(), None) == "City of Portland"


def test_geography_active_summary_with_label():
    assert (
        geography_active_summary({"type": "Polygon"}, "Portland, Oregon")
        == "Portland, Oregon"
    )


def test_geography_active_summary_without_label():
    assert geography_active_summary({"type": "Polygon"}, None) == "Area selected"


def test_truncate_summary():
    assert truncate_summary("A" * 40, max_len=10) == "AAAAAAAAA…"


def test_truncate_summary_default_length():
    long_name = "AmeriCorps Office of Inspector General"
    assert truncate_summary(long_name) == long_name


def test_truncate_summary_truncates_beyond_default():
    long_name = "A" * 60
    assert truncate_summary(long_name) == f"{'A' * 47}…"


def test_publisher_active_summary():
    assert publisher_active_summary("EPA") == "EPA"
