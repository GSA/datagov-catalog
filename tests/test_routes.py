from flask import current_app

def test_search_api_endpoint(interface_with_dataset):
    client = current_app.test_client()
    response = client.get("/search", query_string={"q": "test"})
    print(response.text)
    print(interface_with_dataset.search_datasets("test"))
    print(interface_with_dataset.db, current_app.db)
    assert response.status_code == 200
    assert len(response.json) > 0
