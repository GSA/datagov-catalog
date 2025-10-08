from unittest.mock import patch

from bs4 import BeautifulSoup

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
    rows = soup.select("table tbody tr")

    assert len(rows) == 1

    cells = rows[0].find_all(["th", "td"])
    assert cells[0].get_text(strip=True) == "test org"
    assert cells[1].get_text(strip=True) == "Federal Government"
    assert cells[2].get_text(strip=True) == "1"


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

    tiles = dataset_section.select(".dataset-tile")
    assert len(tiles) == 1

    title_link = tiles[0].find("a")
    assert title_link is not None
    assert title_link.get("href") == "/dataset/test"
    assert title_link.get_text(strip=True) == "test"

    meta_text = tiles[0].select_one(".dataset-tile__meta").get_text(strip=True)
    assert meta_text.startswith("test org -- this is the test description")
