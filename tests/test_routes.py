from unittest.mock import patch
from uuid import uuid4

from bs4 import BeautifulSoup

from app.models import Dataset
from tests.conftest import HARVEST_RECORD_ID


def test_search_api_endpoint(interface_with_dataset, db_client):
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/search", query_string={"q": "test"})
    assert response.status_code == 200
    assert len(response.json) > 0
    assert all("search_vector" not in item for item in response.json)


def test_search_api_pagination(interface_with_dataset, db_client):
    dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
    for i in range(10):
        dataset_dict["id"] = str(i)
        dataset_dict["slug"] = f"test-{i}"
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


def test_dataset_detail_by_slug(interface_with_dataset, db_client):
    """
    Test dataset detail page by using the slug.
    Tests to ensure the page renders correctly and contains expected elements.
    """
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/dataset/test")
    # check response is successful
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    # curently the title of the dataset is in the <title> tag
    assert soup.title.string == "test - Data.gov"
    #  test the current breadcrumb item is the same as the title
    assert (
        soup.find(class_="usa-breadcrumb__list-item usa-current").span.string == "test"
    )
    # assert the title in the h1 section is the same as the title
    h1 = soup.select_one(
        "main#content > div.usa-section > div.grid-container > div.grid-row > div.grid-col-12 > h1.margin-bottom-1"
    ).text
    assert h1 == "test"
    # check the dataset description is present
    description = soup.select_one(
        "main#content > div.usa-section > div.grid-container > .grid-row.grid-gap-lg.margin-top-4 > div > section > p"
    ).text
    assert description == "this is the test description"


def test_dataset_detail_by_id(interface_with_dataset, db_client):
    """
    Similar to test_dataset_detail_by_slug, but uses the dataset ID. This helps
    to ensure that our polymorphic approach works correctly when datasets
    are accessed by ID instead of slug.
    """
    with patch("app.routes.interface", interface_with_dataset):
        dataset_id = interface_with_dataset.get_dataset_by_slug("test").id
        response = db_client.get(f"/dataset/{dataset_id}")
    # check response is successful
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    # curently the title of the dataset is in the <title> tag
    assert soup.title.string == "test - Data.gov"
    #  test the current breadcrumb item is the same as the title
    assert (
        soup.find(class_="usa-breadcrumb__list-item usa-current").span.string == "test"
    )
    # assert the title in the h1 section is the same as the title
    h1 = soup.select_one(
        "main#content > div.usa-section > div.grid-container > div.grid-row > div.grid-col-12 > h1.margin-bottom-1"
    ).text
    assert h1 == "test"
    # check the dataset description is present
    description = soup.select_one(
        "main#content > div.usa-section > div.grid-container > .grid-row.grid-gap-lg.margin-top-4 > div > section > p"
    ).text
    assert description == "this is the test description"


def test_dataset_detail_404(db_client):
    """
    Test that accessing a non-existent dataset by slug or ID returns a 404 error.
    """
    response = db_client.get("/dataset/does-not-exist")
    # check response fails with 404
    assert response.status_code == 404


def test_organization_list_shows_type_and_count(
    db_client, interface_with_dataset
):
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/organization")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select(".organization-list .usa-card")

    assert len(cards) == 1

    card = cards[0]
    heading = card.select_one(".usa-card__heading").get_text(strip=True)
    assert heading == "test org"

    body_paragraphs = card.select(".usa-card__body p")
    assert len(body_paragraphs) >= 2

    type_text = body_paragraphs[0].get_text(" ", strip=True)
    assert type_text.startswith("Type:")
    assert type_text.endswith("Federal Government")

    datasets_text = body_paragraphs[1].get_text(" ", strip=True)
    assert datasets_text.startswith("Datasets:")
    assert datasets_text.endswith("1")


def test_organization_detail_displays_dataset_list(
    db_client, interface_with_dataset
):
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/organization/test-org")

    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    dataset_section = soup.find("section", class_="organization-datasets")
    assert dataset_section is not None

    heading_text = dataset_section.find("h2").get_text(strip=True)
    assert heading_text.endswith("(1)")

    items = dataset_section.select(".usa-collection__item")
    assert len(items) == 1

    item = items[0]
    title_link = item.select_one(".usa-collection__heading a")
    assert title_link is not None
    assert title_link.get("href") == "/dataset/test"
    assert title_link.get_text(strip=True) == "test"

    meta_items = item.select(".usa-collection__meta-item")
    assert meta_items
    organization_meta_text = meta_items[0].get_text(" ", strip=True)
    assert organization_meta_text.startswith("Organization:")
    assert organization_meta_text.endswith("test org")

    description_text = item.select_one(".usa-collection__description").get_text(strip=True)
    assert description_text.startswith("this is the test description")


def test_harvest_record_raw_returns_json(interface_with_harvest_record, db_client):
    with patch("app.routes.interface", interface_with_harvest_record):
        response = db_client.get(f"/harvest_record/{HARVEST_RECORD_ID}/raw")

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert response.get_data(as_text=True) == '{"title": "test dataset"}'


def test_harvest_record_raw_returns_xml(interface_with_harvest_record, db_client):
    record = interface_with_harvest_record.get_harvest_record(HARVEST_RECORD_ID)
    record.source_raw = "<xml>value</xml>"
    interface_with_harvest_record.db.commit()

    with patch("app.routes.interface", interface_with_harvest_record):
        response = db_client.get(f"/harvest_record/{HARVEST_RECORD_ID}/raw")

    assert response.status_code == 200
    assert response.mimetype == "application/xml"
    assert response.get_data(as_text=True) == "<xml>value</xml>"


def test_harvest_record_raw_not_found(interface_with_harvest_record, db_client):
    missing_id = str(uuid4())
    with patch("app.routes.interface", interface_with_harvest_record):
        response = db_client.get(f"/harvest_record/{missing_id}/raw")

    assert response.status_code == 404


def test_harvest_record_transformed_returns_json(
    interface_with_harvest_record, db_client
):
    with patch("app.routes.interface", interface_with_harvest_record):
        response = db_client.get(
            f"/harvest_record/{HARVEST_RECORD_ID}/transformed"
        )

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert response.get_json() == {
        "title": "test dataset",
        "extras": {"foo": "bar"},
    }


def test_harvest_record_transformed_not_found(
    interface_with_harvest_record, db_client
):
    record = interface_with_harvest_record.get_harvest_record(HARVEST_RECORD_ID)
    record.source_transform = None
    interface_with_harvest_record.db.commit()

    with patch("app.routes.interface", interface_with_harvest_record):
        response = db_client.get(
            f"/harvest_record/{HARVEST_RECORD_ID}/transformed"
        )

    assert response.status_code == 404
