from unittest.mock import patch

from bs4 import BeautifulSoup


def test_search_result_card_shows_related_records_badge_for_parent(
    interface_with_dataset, db_client
):
    """A dataset with indexed children (via parent_identifier) should show
    a "Related Records" badge on its search result card."""
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/?q=Parent+Harvest+Record")

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    first_item = soup.find("li", class_="usa-collection__item")
    assert first_item is not None
    assert first_item.select_one("i.collection-icon") is not None
    assert "Related Records" in first_item.get_text()


def test_search_result_card_has_no_badge_without_children(
    interface_with_dataset, db_client
):
    """A dataset with no children/collection role shows no collection badge."""
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/?q=Health+Food+Access+Statistics")

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    first_item = soup.find("li", class_="usa-collection__item")
    assert first_item is not None
    assert first_item.select_one("i.collection-icon") is None
