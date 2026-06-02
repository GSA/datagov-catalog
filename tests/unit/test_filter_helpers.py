from app.filter_helpers import (
    TOP_PUBLISHER_COMBO_SIZE,
    publisher_combo_select_names,
    publisher_names_from_top_publishers,
)


def test_publisher_names_from_top_publishers_sorted():
    top = [{"name": "Zebra Pub", "count": 1}, {"name": "Alpha Pub", "count": 2}]
    assert publisher_names_from_top_publishers(top) == ["Alpha Pub", "Zebra Pub"]


def test_publisher_combo_select_names_dedupes_and_includes_extras():
    top = [{"name": "Alpha Pub", "count": 2}, {"name": "Beta Pub", "count": 1}]
    names = publisher_combo_select_names(
        top,
        suggested=["Gamma Pub", "Alpha Pub"],
        selected="Delta Pub",
    )
    assert names == ["Alpha Pub", "Beta Pub", "Gamma Pub", "Delta Pub"]


def test_top_publisher_combo_size_matches_interface_cap():
    assert TOP_PUBLISHER_COMBO_SIZE == 100
