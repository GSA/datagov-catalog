from unittest.mock import patch

from bs4 import BeautifulSoup

from app.models import Dataset


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


def test_organization_list_shows_type_and_count(db_client, interface_with_dataset):
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


def test_organization_detail_displays_dataset_list(db_client, interface_with_dataset):
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

    description_text = item.select_one(".usa-collection__description").get_text(
        strip=True
    )
    assert description_text.startswith("this is the test description")

def test_index_page_renders(db_client):
    """
    Test that the index page loads correctly and contains the search form.
    """
    response = db_client.get("/")
    assert response.status_code == 200
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Check page title
    assert "Catalog - Data.gov" in soup.title.string
    
    # Check search form exists with all of the expected elements
    search_form = soup.find("form", {"hx-get": True})
    assert search_form is not None    
    search_input = soup.find("input", {"id": "search-query", "name": "q"})
    assert search_input is not None
    search_button = soup.find("button", {"type": "submit"})
    assert search_button is not None
    
    # Check search results container exists (initially empty)
    results_container = soup.find("div", {"id": "search-results"})
    assert results_container is not None

def test_index_search_returns_results(interface_with_dataset, db_client):
    """
    Test that searching via HTMX returns HTML results with dataset information.
    """
    with patch("app.routes.interface", interface_with_dataset):
        # Simulate HTMX request with HX-Request header
        response = db_client.get(
            "/search",
            query_string={"q": "test", "paginate": "false", "per_page": "20"},
            headers={"HX-Request": "true"}
        )
    
    assert response.status_code == 200
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Check that search results container is returned
    results_container = soup.find("div", {"id": "search-results"})
    assert results_container is not None
    
    # Check that results count is displayed
    results_text = soup.find("p", class_="text-base-dark")
    assert results_text is not None
    assert "Found" in results_text.text
    assert "dataset(s)" in results_text.text
    
    # Check that dataset is in the results
    dataset_collection = soup.find("ul", class_="usa-collection")
    assert dataset_collection is not None
    
    dataset_items = dataset_collection.find_all("li", class_="usa-collection__item")
    assert len(dataset_items) > 0
    
    # Check first dataset has expected elements
    first_dataset = dataset_items[0]
    dataset_heading = first_dataset.find("h3", class_="usa-collection__heading")
    assert dataset_heading is not None
    assert "test" in dataset_heading.text.lower()
    
    # Check dataset has description
    dataset_description = first_dataset.find("p", class_="usa-collection__description")
    assert dataset_description is not None
