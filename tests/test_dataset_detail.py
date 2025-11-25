from unittest.mock import patch

from bs4 import BeautifulSoup

from app.utils import hint_from_dict
from tests.fixtures import DATASET_ID


class TestDatasetDetail:
    """
    Test cases for dataset detail page.
    """

    def test_dataset_detail_by_slug(self, interface_with_dataset):
        dataset = interface_with_dataset.get_dataset_by_slug("test")
        assert dataset is not None
        assert dataset.dcat.get("title") == "test"

    def test_dataset_detail_by_id(self, interface_with_dataset):
        dataset = interface_with_dataset.get_dataset_by_id(DATASET_ID)
        assert dataset is not None
        assert dataset.dcat.get("title") == "test"

    def test_dataset_detail_return_to_search(self, interface_with_dataset, db_client):
        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get(
                "/dataset/test", query_string={"from_hint": hint_from_dict({"a": "b"})}
            )
        soup = BeautifulSoup(response.text, "html.parser")
        back_link = soup.find("a", class_="return-link")
        assert back_link is not None
        assert "?a=b" in back_link.get("href")
