from app.filters import remove_html_tags


def test_remove_html_tags(html_tags_within_text):
    assert (
        remove_html_tags(html_tags_within_text)
        == "The Division of Drinking Water requires laboratories to \n    submit water quality data directly. The data is received, and published \n    twice monthly on the Division's water quality \n    \n    portal. The resource here now is just a data dictionary for the \n    laboratory analysis data available from that portal, and in the near \n    future we plan to add curated data resources that include laboratory\n    water quality results."
    )


def test_lt_or_gt_not_removed():
    assert remove_html_tags("in x < 0, but also y > 0") == "in x < 0, but also y > 0"
