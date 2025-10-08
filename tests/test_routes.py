from unittest.mock import patch

from app.models import Dataset


def test_search_api_endpoint(interface_with_dataset, db_client):
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/search", query_string={"q": "test"})
    assert response.status_code == 200
    assert len(response.json) > 0


def test_search_api_pagination(interface_with_dataset, db_client):
    dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
    for i in range(10):
        dataset_dict["id"] = str(i)
        interface_with_dataset.db.add(Dataset(**dataset_dict))
    interface_with_dataset.db.commit()
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/search", query_string={"q": "test", "per_page": "5"})
        assert len(response.json) == 5

        response = db_client.get(
            "/search", query_string={"q": "test", "paginate": "false"}
        )
        # one original dataset plus 10 new ones
        assert len(response.json) == 11
