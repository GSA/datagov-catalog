from tests.conftest import DATASET_ID


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
