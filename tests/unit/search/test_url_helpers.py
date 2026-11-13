from app.search import url_helpers


def test_criteria_url_for_percent_encodes_spaces(monkeypatch):
    monkeypatch.setattr(
        url_helpers,
        "url_for",
        lambda endpoint, **values: "/?q=Select+Hydrologic&literal_plus=%2B",
    )

    result = url_helpers.criteria_url_for("main.index", q="Select Hydrologic")

    assert result == "/?q=Select%20Hydrologic&literal_plus=%2B"
