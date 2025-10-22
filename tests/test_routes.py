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
    description = soup.select_one(".dataset-detail__description-text").get_text(strip=True)
    assert description == "this is the test description"

    feedback_button = soup.find("button", id="contact-btn")
    assert feedback_button is not None
    assert feedback_button.get("data-dataset-identifier") == "test"
    assert "Feedback" in feedback_button.get_text(" ", strip=True)

    resources_heading = soup.find("h2", string="Resources")
    assert resources_heading is not None

    resources_table = resources_heading.find_next("table")
    assert resources_table is not None

    rows = resources_table.select("tbody tr")
    assert len(rows) == 1

    first_row = rows[0]
    resource_cell = first_row.find("th")
    assert "Test CSV" in resource_cell.get_text(" ", strip=True)

    resource_link = resource_cell.find("a")
    assert resource_link is not None
    assert resource_link.get("href") == "https://example.com/test.csv"

    format_cell, access_cell = first_row.find_all("td")
    assert format_cell.get_text(" ", strip=True) == "CSV"
    assert access_cell.find("a").get_text(strip=True) == "Download"


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
    description = soup.select_one(".dataset-detail__description-text").get_text(strip=True)
    assert description == "this is the test description"

    feedback_button = soup.find("button", id="contact-btn")
    assert feedback_button is not None
    assert feedback_button.get("data-dataset-identifier") == "test"
    assert "Feedback" in feedback_button.get_text(" ", strip=True)

    resources_heading = soup.find("h2", string="Resources")
    assert resources_heading is not None

    resources_table = resources_heading.find_next("table")
    assert resources_table is not None

    rows = resources_table.select("tbody tr")
    assert len(rows) == 1

    first_row = rows[0]
    resource_cell = first_row.find("th")
    assert "Test CSV" in resource_cell.get_text(" ", strip=True)

    resource_link = resource_cell.find("a")
    assert resource_link is not None
    assert resource_link.get("href") == "https://example.com/test.csv"

    format_cell, access_cell = first_row.find_all("td")
    assert format_cell.get_text(" ", strip=True) == "CSV"
    assert access_cell.find("a").get_text(strip=True) == "Download"


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
    assert datasets_text.endswith("49")


def test_organization_detail_displays_dataset_list(db_client, interface_with_dataset):
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/organization/test-org")

    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    dataset_section = soup.find("section", class_="organization-datasets")
    assert dataset_section is not None

    search_button = soup.find("form", attrs={"action": "/organization/test-org"})
    assert search_button is not None

    heading_text = dataset_section.find("h2").get_text(strip=True)
    assert heading_text.endswith("(49)")

    items = dataset_section.select(".usa-collection__item")
    assert len(items) == 20

    item = items[0]
    title_link = item.select_one(".usa-collection__heading a")
    assert title_link is not None
    assert title_link.get("href") == "/dataset/segal-americorps-education-award-detailed-payments-by-institution-2020"
    assert title_link.get_text(strip=True) == "Segal AmeriCorps Education Award: Detailed Payments by Institution 2020"

    meta_items = item.select(".usa-collection__meta-item")
    assert meta_items
    organization_meta_text = meta_items[0].get_text(" ", strip=True)
    assert organization_meta_text.startswith("Organization:")
    assert organization_meta_text.endswith("test org")

    description_text = item.select_one(".usa-collection__description").get_text(
        strip=True
    )
    assert description_text.startswith("Summary dataset of detailed payments")


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
            headers={"HX-Request": "true"},
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


def test_index_search_with_pagination(interface_with_dataset, db_client):
    """
    Test that search results with pagination render correctly via HTMX.
    Creates multiple datasets to trigger pagination display.
    """
    # Create multiple datasets to ensure pagination appears
    dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
    for i in range(25):  # Create enough for multiple pages
        dataset_dict["id"] = str(i)
        dataset_dict["slug"] = f"test-{i}"
        dataset_dict["dcat"]["title"] = f"Test Dataset {i}"
        interface_with_dataset.db.add(Dataset(**dataset_dict))
    # attempt commit
    interface_with_dataset.db.commit()

    with patch("app.routes.interface", interface_with_dataset):
        # Request page 1 with 20 items per page
        response = db_client.get(
            "/search",
            query_string={
                "q": "test",
                "paginate": "false",
                "per_page": "20",
                "page": "1",
            },
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")

    # Check pagination exists
    pagination = soup.find("nav", class_="usa-pagination")
    assert pagination is not None

    # Check pagination has page numbers
    pagination_list = pagination.find("ul", class_="usa-pagination__list")
    assert pagination_list is not None

    # Check for current page indicator
    current_page = pagination.find("span", class_="usa-current")
    assert current_page is not None
    assert "1" in current_page.text

    # Check for Next button and ensure htmx attrs are there
    next_button = pagination.find("a", class_="usa-pagination__next-page")
    assert next_button is not None
    assert "hx-get" in next_button.attrs
    assert "hx-target" in next_button.attrs


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
        response = db_client.get(f"/harvest_record/{HARVEST_RECORD_ID}/transformed")

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert response.get_json() == {
        "title": "test dataset",
        "extras": {"foo": "bar"},
    }


def test_harvest_record_transformed_not_found(interface_with_harvest_record, db_client):
    record = interface_with_harvest_record.get_harvest_record(HARVEST_RECORD_ID)
    record.source_transform = None
    interface_with_harvest_record.db.commit()

    with patch("app.routes.interface", interface_with_harvest_record):
        response = db_client.get(f"/harvest_record/{HARVEST_RECORD_ID}/transformed")

    assert response.status_code == 404


def test_organization_detail_displays_searched_dataset_no_pagination(
    db_client, interface_with_dataset
):
    """
    search for datasets within the org fewer than the pagination count. the expectation
    is only 4 datasets are returned based on the search so pagination shouldn't appear
    because it's less than the default 20
    """
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/organization/test-org?dataset_search_terms=2016")

    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    dataset_section = soup.find("section", class_="organization-datasets")
    assert dataset_section is not None

    items = dataset_section.select(".usa-collection__item")
    assert len(items) == 4

    pages = soup.find_all("li", class_="usa-pagination__item usa-pagination__page-no")
    assert len(pages) == 0

    item = items[0]
    title_link = item.select_one(".usa-collection__heading a")
    assert title_link is not None
    assert title_link.get("href") == "/dataset/2016-americorps-mes-americorps-member-exit-survey"
    assert title_link.get_text(strip=True) == "2016 AmeriCorps MES: AmeriCorps Member Exit Survey"


def test_organization_detail_displays_searched_dataset_with_pagination(
    db_client, interface_with_dataset
):
    """
    search for datasets within an org larger than the pagination count. the expectation is
    pagination occurs, the first page has 20 datasets, and there's 3 pages (the search 
    without pagination returns 47 datasets)
    
    """
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/organization/test-org?dataset_search_terms=americorps")

    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    dataset_section = soup.find("section", class_="organization-datasets")
    assert dataset_section is not None

    items = dataset_section.select(".usa-collection__item")
    assert len(items) == 20

    pages = soup.find_all("li", class_="usa-pagination__item usa-pagination__page-no")
    assert len(pages) == 3


def test_organization_detail_displays_no_datasets_on_search(
    db_client, interface_with_dataset
):
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get(
            "/organization/test-org?dataset_search_terms=no-dataset"
        )

    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    dataset_section = soup.find("section", class_="organization-datasets")
    assert dataset_section is not None

    items = dataset_section.select(".usa-collection__item")
    assert len(items) == 0
