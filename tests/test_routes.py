import json
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
    description = soup.select_one(".dataset-detail__description-text").get_text(
        strip=True
    )
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

    search_form = soup.find("form", attrs={"action": "/"})
    assert search_form is not None
    search_input = search_form.find("input", {"name": "q"})
    assert search_input is not None
    submit_button = search_form.find("button", {"type": "submit"})
    assert submit_button is not None
    assert "Search" in submit_button.get_text(" ", strip=True)


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
    description = soup.select_one(".dataset-detail__description-text").get_text(
        strip=True
    )
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

    search_form = soup.find("form", attrs={"action": "/"})
    assert search_form is not None
    search_input = search_form.find("input", {"name": "q"})
    assert search_input is not None


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
    assert (
        title_link.get("href")
        == "/dataset/segal-americorps-education-award-detailed-payments-by-institution-2020"
    )
    assert (
        title_link.get_text(strip=True)
        == "Segal AmeriCorps Education Award: Detailed Payments by Institution 2020"
    )

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

    # Check search form exists with expected attributes
    main_search_input = soup.find("input", {"id": "search-query", "name": "q"})
    assert main_search_input is not None

    # Find the form that contains this input (the main search form)
    search_form = main_search_input.find_parent("form")
    assert search_form is not None
    assert search_form.get("method", "").lower() == "get"

    search_input = search_form.find("input", {"id": "search-query", "name": "q"})
    assert search_input is not None

    per_page_input = search_form.find("input", {"type": "hidden", "name": "per_page"})
    assert per_page_input is not None

    search_button = search_form.find("button", {"type": "submit"})
    assert search_button is not None

    # Initial load should not render results without a query
    assert soup.find("div", {"id": "search-results"}) is None


def test_index_search_returns_results(interface_with_dataset, db_client):
    """
    Test that searching via HTMX returns HTML results with dataset information.
    """
    with patch("app.routes.interface", interface_with_dataset):
        # Simulate HTMX request with HX-Request header
        response = db_client.get(
            "/search",
            query_string={"q": "test", "count": "true", "per_page": "20"},
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
            query_string={"q": "test", "count": "true", "per_page": "20", "page": "1"},
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
    assert (
        title_link.get("href")
        == "/dataset/2016-americorps-mes-americorps-member-exit-survey"
    )
    assert (
        title_link.get_text(strip=True)
        == "2016 AmeriCorps MES: AmeriCorps Member Exit Survey"
    )


def test_organization_detail_displays_searched_dataset_with_pagination(
    db_client, interface_with_dataset
):
    """
    search for datasets within an org larger than the pagination count. the expectation is
    pagination occurs, the first page has 20 datasets, and there's 3 pages (the search
    without pagination returns 47 datasets)

    """
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get(
            "/organization/test-org?dataset_search_terms=americorps"
        )

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


def test_index_page_empty_query_shows_no_results(db_client):
    """Test that index page with no search query shows no results section."""
    response = db_client.get("/")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")

    # Should not show results container when no query
    results_text = soup.find("p", class_="text-base-dark")
    assert results_text is None


def test_index_page_has_filters_sidebar(db_client):
    """Test that the index page contains the filters sidebar."""
    response = db_client.get("/")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")

    # Check for sort dropdown
    sort_select = soup.find("select", {"name": "sort", "id": "sort-select"})
    assert sort_select is not None

    # Check sort has relevance option
    relevance_option = soup.find("option", {"value": "relevance"})
    assert relevance_option is not None

    # Check for organization type filters
    filter_form = soup.find("form", {"id": "filter-form"})
    assert filter_form is not None

    # Check for specific organization type checkboxes
    federal_checkbox = soup.find(
        "input", {"id": "filter-federal", "value": "Federal Government"}
    )
    assert federal_checkbox is not None
    assert federal_checkbox.get("type") == "checkbox"

    city_checkbox = soup.find(
        "input", {"id": "filter-city", "value": "City Government"}
    )
    assert city_checkbox is not None

    state_checkbox = soup.find(
        "input", {"id": "filter-state", "value": "State Government"}
    )
    assert state_checkbox is not None


def test_index_page_query_parameter_preserved_in_form(db_client):
    """Test that query parameters are preserved in the search form."""
    response = db_client.get("/?q=climate&per_page=10&sort=relevance")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")

    # Check search input has the query value
    search_input = soup.find("input", {"name": "q"})
    assert search_input is not None
    assert search_input.get("value") == "climate"

    # Check hidden inputs preserve other parameters
    per_page_input = soup.find("input", {"name": "per_page", "type": "hidden"})
    assert per_page_input is not None
    assert per_page_input.get("value") == "10"

    sort_input = soup.find("input", {"name": "sort", "type": "hidden"})
    assert sort_input is not None
    assert sort_input.get("value") == "relevance"


def test_index_search_with_query_shows_result_count(interface_with_dataset, db_client):
    """Test that searching shows the count of results found."""
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/?q=test")

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    # Check for results count message
    results_text = soup.find("p", class_="text-base-dark")
    assert results_text is not None
    assert "Found" in results_text.text
    assert "dataset(s)" in results_text.text
    assert 'matching "test"' in results_text.text


def test_index_search_result_includes_organization_link(
    interface_with_dataset, db_client
):
    """Test that each search result includes a link to the organization."""
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/?q=test")

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    # Find first dataset item
    first_item = soup.find("li", class_="usa-collection__item")
    assert first_item is not None

    # Check for organization link in metadata
    org_link = first_item.find("a", href=lambda href: href and "/organization/" in href)
    assert org_link is not None
    assert "test org" in org_link.text


def test_index_search_result_includes_dataset_link(interface_with_dataset, db_client):
    """Test that each search result includes a link to the dataset detail page."""
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/?q=test")

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    # Find first dataset item
    first_item = soup.find("li", class_="usa-collection__item")
    assert first_item is not None

    # Check for dataset link
    dataset_link = first_item.find("a", href=lambda href: href and "/dataset/" in href)
    assert dataset_link is not None


def test_index_pagination_preserves_query_params(interface_with_dataset, db_client):
    """Test that pagination links preserve query and filter parameters."""
    # Create multiple datasets for pagination
    dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
    for i in range(25):
        dataset_dict["id"] = str(i)
        dataset_dict["slug"] = f"test-{i}"
        interface_with_dataset.db.add(Dataset(**dataset_dict))
    interface_with_dataset.db.commit()

    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/?q=test&per_page=10&sort=relevance")

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    # Check that pagination links preserve parameters
    next_link = soup.find("a", class_="usa-pagination__next-page")
    if next_link:
        href = next_link.get("href")
        assert "q=test" in href
        assert "per_page=10" in href
        assert "sort=relevance" in href


def test_index_filter_checkboxes_checked_when_selected(db_client):
    """Test that filter checkboxes are checked when organization types are selected."""
    response = db_client.get(
        "/?q=test&org_type=Federal+Government&org_type=State+Government"
    )
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")

    # Check Federal Government checkbox is checked
    federal_checkbox = soup.find("input", {"id": "filter-federal"})
    assert federal_checkbox is not None
    assert "checked" in federal_checkbox.attrs

    # Check State Government checkbox is checked
    state_checkbox = soup.find("input", {"id": "filter-state"})
    assert state_checkbox is not None
    assert "checked" in state_checkbox.attrs

    # Check City Government checkbox is NOT checked
    city_checkbox = soup.find("input", {"id": "filter-city"})
    assert city_checkbox is not None
    assert "checked" not in city_checkbox.attrs


def test_index_apply_filters_button_exists(db_client):
    """Test that the Apply Filters button exists in the sidebar."""
    response = db_client.get("/")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")

    apply_button = soup.find(
        "button", {"type": "submit"}, string=lambda s: s and "Apply Filters" in s
    )
    assert apply_button is not None
    assert "usa-button" in apply_button.get("class", [])


def test_header_exists(db_client):
    response = db_client.get("/")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")

    # check for usa banner
    usa_banner = soup.find("section", class_="usa-banner")
    assert usa_banner is not None

    # check for navigation and nav parts
    nav_bar = soup.find("div", class_="usa-navbar")
    assert nav_bar is not None

    nav_parts = soup.find_all("li", class_="usa-nav__primary-item")
    assert len(nav_parts) == 3  # "Home", "Organizations", "User Guide"


def test_footer_exists(db_client):
    response = db_client.get("/")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")

    datagov_footer = soup.find("div", class_="footer-section-bottom")
    assert datagov_footer is not None

    gsa_footer = soup.find("div", class_="usa-identifier")
    assert gsa_footer is not None


def test_dataset_detail_includes_map_assets_when_spatial_bbox(
    interface_with_dataset, db_client
):
    # Add spatial bbox and ensure map container and Leaflet assets are present
    ds = interface_with_dataset.get_dataset_by_slug("test")
    ds.dcat["spatial"] = "-90.155,27.155,-90.26,27.255"
    interface_with_dataset.db.commit()

    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/dataset/test")

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    # Map container
    map_div = soup.select_one("#dataset-map")
    assert map_div is not None
    assert map_div.get("data-bbox") == "-90.155,27.155,-90.26,27.255"

    # Leaflet assets (conditionally included)
    leaflet_css = soup.select_one('link[href*="leaflet.css"]')
    leaflet_js = soup.select_one('script[src*="leaflet.js"]')
    view_js = soup.select_one('script[src*="js/view_bbox_map.js"]')
    assert leaflet_css is not None
    assert leaflet_js is not None
    assert view_js is not None


def test_dataset_detail_includes_map_assets_when_spatial_geometry(
    interface_with_dataset, db_client
):
    # Add spatial geometry and ensure map container and Leaflet assets are present
    ds = interface_with_dataset.get_dataset_by_slug("test")
    ds.dcat["spatial"] = {
        "type": "Polygon",
        "coordinates": [
            [
                [-373.59375715256, -65.778772326728],
                [-373.59375715256, 84.220160826965],
                [-12.187442779541, 84.220160826965],
                [-12.187442779541, -65.778772326728],
                [-373.59375715256, -65.778772326728],
            ]
        ],
    }
    interface_with_dataset.db.commit()

    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/dataset/test")

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    map_div = soup.select_one("#dataset-map")
    assert map_div is not None
    assert map_div.get("data-bbox") is None

    geometry_attr = map_div.get("data-geometry")
    assert geometry_attr is not None
    assert json.loads(geometry_attr) == ds.dcat["spatial"]

    leaflet_css = soup.select_one('link[href*="leaflet.css"]')
    leaflet_js = soup.select_one('script[src*="leaflet.js"]')
    view_js = soup.select_one('script[src*="js/view_bbox_map.js"]')
    assert leaflet_css is not None
    assert leaflet_js is not None
    assert view_js is not None


def test_dataset_detail_includes_map_assets_when_spatial_geometry_string(
    interface_with_dataset, db_client
):
    ds = interface_with_dataset.get_dataset_by_slug("test")
    geometry = {
        "type": "Polygon",
        "coordinates": [
            [
                [-373.59375715256, -65.778772326728],
                [-373.59375715256, 84.220160826965],
                [-12.187442779541, 84.220160826965],
                [-12.187442779541, -65.778772326728],
                [-373.59375715256, -65.778772326728],
            ]
        ],
    }
    ds.dcat["spatial"] = json.dumps(geometry)
    interface_with_dataset.db.commit()

    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/dataset/test")

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    map_div = soup.select_one("#dataset-map")
    assert map_div is not None
    assert map_div.get("data-bbox") is None

    geometry_attr = map_div.get("data-geometry")
    assert geometry_attr is not None
    assert json.loads(geometry_attr) == geometry

    leaflet_css = soup.select_one('link[href*="leaflet.css"]')
    leaflet_js = soup.select_one('script[src*="leaflet.js"]')
    view_js = soup.select_one('script[src*="js/view_bbox_map.js"]')
    assert leaflet_css is not None
    assert leaflet_js is not None
    assert view_js is not None


def test_dataset_detail_omits_map_when_spatial_missing(
    interface_with_dataset, db_client
):
    # Ensure no spatial key and verify no map container or Leaflet assets
    ds = interface_with_dataset.get_dataset_by_slug("test")
    ds.dcat.pop("spatial", None)
    interface_with_dataset.db.commit()

    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/dataset/test")

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    # No map container
    assert soup.select_one("#dataset-map") is None

    # No Leaflet assets
    assert soup.select_one('link[href*="leaflet.css"]') is None
    assert soup.select_one('script[src*="leaflet.js"]') is None
    assert soup.select_one('script[src*="js/view_bbox_map.js"]') is None


def test_dataset_detail_logs_warning_when_spatial_unqualified(
    interface_with_dataset, db_client
):
    ds = interface_with_dataset.get_dataset_by_slug("test")
    ds.dcat["spatial"] = "Virginia, USA"
    interface_with_dataset.db.commit()

    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/dataset/test")

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    # Still no map container or assets
    assert soup.select_one("#dataset-map") is None
    assert soup.select_one('link[href*="leaflet.css"]') is None
    assert soup.select_one('script[src*="leaflet.js"]') is None
    assert soup.select_one('script[src*="js/view_bbox_map.js"]') is None

    inline_scripts = [
        script.get_text() for script in soup.find_all("script") if not script.get("src")
    ]
    assert any("Map not displayed" in content for content in inline_scripts)
