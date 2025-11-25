import json
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from bs4 import BeautifulSoup

from app.database.opensearch import SearchResult
from app.models import Dataset
from tests.fixtures import HARVEST_RECORD_ID


def test_search_api_endpoint(interface_with_dataset, db_client):
    # search relies on Opensearch now
    interface_with_dataset.opensearch.index_datasets(
        interface_with_dataset.db.query(Dataset)
    )
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/search", query_string={"q": "test"})
    assert response.status_code == 200
    assert len(response.json) > 0
    assert all("search_vector" not in item for item in response.json)
    assert "results" in response.json


def test_search_api_pagination(interface_with_dataset, db_client):
    dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
    for i in range(10):
        dataset_dict["id"] = str(i)
        dataset_dict["slug"] = f"test-{i}"
        dataset_dict["dcat"] = {"title": "test-{i}"}
        interface_with_dataset.db.add(Dataset(**dataset_dict))
    interface_with_dataset.db.commit()
    # search relies on Opensearch now
    interface_with_dataset.opensearch.index_datasets(
        interface_with_dataset.db.query(Dataset)
    )
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/search", query_string={"q": "test", "per_page": "5"})
        assert len(response.json["results"]) == 5
        assert "after" in response.json

        response = db_client.get("/search", query_string={"q": "test"})
        # default page size is 20 elements but there are at least 11 datasets
        assert len(response.json["results"]) >= 11


def test_search_api_paginate_after(interface_with_dataset, db_client):
    dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
    for i in range(10):
        dataset_dict["id"] = str(i)
        dataset_dict["slug"] = f"test-{i}"
        dataset_dict["dcat"] = {"title": f"test-{i}"}
        interface_with_dataset.db.add(Dataset(**dataset_dict))
    interface_with_dataset.db.commit()
    # search relies on Opensearch now
    interface_with_dataset.opensearch.index_datasets(
        interface_with_dataset.db.query(Dataset)
    )
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/search", query_string={"q": "test", "per_page": "1"})
        previous_slug = response.json["results"][0]["slug"]
        assert len(response.json["results"]) == 1
        assert "after" in response.json
        after = response.json["after"]
        # we made 10 new datasets, so we can follow the "after" 9 times and
        # still have an "after"
        for i in range(9):
            response = db_client.get(
                "/search", query_string={"q": "test", "per_page": "1", "after": after}
            )
            assert response.status_code == 200
            assert len(response.json["results"]) == 1
            assert "after" in response.json
            assert response.json["results"][0]["slug"] != previous_slug
            previous_slug = response.json["results"][0]["slug"]
            after = response.json["after"]


def test_search_api_by_org_id(interface_with_dataset, db_client):
    with patch("app.routes.interface", interface_with_dataset):
        # test org has id "1"
        response = db_client.get("/search", query_string={"q": "test", "org_id": "1"})
        assert len(response.json["results"]) > 0

        # non-existent org
        response = db_client.get(
            "/search", query_string={"q": "test", "org_id": "non-existent"}
        )
        assert len(response.json["results"]) == 0


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
    # assert the title in the h1 section is the same as the title
    h1 = soup.select_one("main#content h1.dataset-title").text
    assert h1 == "test"
    # check the dataset description is present
    description = soup.select_one(".dataset-description").get_text(strip=True)
    assert description == "this is the test description"

    feedback_button = soup.find("button", id="contact-btn")
    assert feedback_button is not None
    assert feedback_button.get("data-dataset-identifier") == "test"
    assert "Feedback" in feedback_button.get_text(" ", strip=True)

    resources_heading = soup.select_one("h3.sidebar-section__heading")
    assert resources_heading is not None

    resources_details = soup.select_one("details.resources-dropdown")
    assert resources_details is not None

    resources = resources_details.select("ul li")
    assert len(resources) == 1

    first_resource = resources[0]
    resource_name = first_resource.select_one(".resources-list__name")
    assert "Test CSV" in resource_name.get_text(" ", strip=True)

    resource_link = first_resource.find("a")
    assert resource_link is not None
    assert resource_link.get("href") == "https://example.com/test.csv"

    search_form = soup.find("form", attrs={"action": "/"})
    assert search_form is not None
    search_input = search_form.find("input", {"name": "q"})
    assert search_input is not None


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
    # assert the title in the h1 section is the same as the title
    h1 = soup.select_one("main#content h1.dataset-title").text
    assert h1 == "test"
    # check the dataset description is present
    description = soup.select_one(".dataset-description").get_text(strip=True)
    assert description == "this is the test description"

    feedback_button = soup.find("button", id="contact-btn")
    assert feedback_button is not None
    assert feedback_button.get("data-dataset-identifier") == "test"
    assert "Feedback" in feedback_button.get_text(" ", strip=True)

    resources_heading = soup.select_one("h3.sidebar-section__heading")
    assert resources_heading is not None

    resources_details = soup.select_one("details.resources-dropdown")
    assert resources_details is not None

    resources = resources_details.select("ul li")
    assert len(resources) == 1

    first_resource = resources[0]
    resource_name = first_resource.select_one(".resources-list__name")
    assert "Test CSV" in resource_name.get_text(" ", strip=True)

    resource_link = first_resource.find("a")
    assert resource_link is not None
    assert resource_link.get("href") == "https://example.com/test.csv"

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

    # "test org filtered" is removed because it has no datasets
    # leaving only 1 organization present
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

    default_icon = card.find("svg", class_="default-gov-svg-org-item")
    assert default_icon is not None


def test_organization_list_search_empty(db_client, interface_with_dataset):
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/organization?q=nonexistentsearchterm")
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select(".organization-list .usa-card")
    assert not cards  # list is empty


def test_organization_list_search_by_alias(db_client, interface_with_dataset):
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/organization?q=aliasonly")
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select(".organization-list .usa-card")

    # one org still appears
    assert len(cards) == 1


def test_organization_detail_displays_dataset_list(db_client, interface_with_dataset):
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/organization/test-org")

    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    dataset_section = soup.find("section", class_="organization-datasets")
    assert dataset_section is not None

    search_button = soup.find("form", attrs={"action": "/organization/test-org"})
    assert search_button is not None

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

    assert soup.find(text="Search Data.gov") is None

    # Check search form exists with expected attributes
    main_search_input = soup.find("input", {"id": "search-query", "name": "q"})
    assert main_search_input is not None

    # Find the form that contains this input (the main search form)
    search_form = main_search_input.find_parent("form")
    assert search_form is not None
    assert search_form.get("method", "").lower() == "get"

    search_input = search_form.find("input", {"id": "search-query", "name": "q"})
    assert search_input is not None

    search_button = search_form.find("button", {"type": "submit"})
    assert search_button is not None

    # misc dataset checks
    org_banner = soup.find("div", class_="dataset-org-banner")
    assert org_banner is not None
    assert org_banner.text == "Federal"

    # default href is the dataset page if accessURL is null
    html_resource = soup.find("a", {"data-format": "html"})
    assert html_resource is not None
    assert (
        html_resource["href"]
        == "/dataset/segal-americorps-education-award-detailed-payments-by-institution-2020"
    )

    # line arrow up is present and has a hover/title with view count
    line_arrow = soup.find("i", class_="fa-arrow-trend-up")
    assert line_arrow is not None


def test_index_page_includes_dataset_total(db_client, interface_with_dataset):
    """
    Test that the index page loads correctly and contains the search form.
    """
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    # includes the dataset count
    dataset_total = soup.find("span", class_="text-heavy")
    assert dataset_total is not None
    print(response.text)
    assert int(dataset_total.text) > 0

def test_htmx_search_returns_results(interface_with_dataset, db_client):
    """
    Test that searching via HTMX returns HTML results with dataset information.
    """
    with patch("app.routes.interface", interface_with_dataset):
        # Simulate HTMX request with HX-Request header
        response = db_client.get(
            "/search",
            query_string={"q": "test", "per_page": "20"},
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")

    # result contains list items
    dataset_items = soup.find_all("li", class_="usa-collection__item")
    assert len(dataset_items) > 0

    # Check first dataset has expected elements
    first_dataset = dataset_items[0]
    dataset_heading = first_dataset.find("h3", class_="usa-collection__heading")
    assert dataset_heading is not None
    assert "test" in dataset_heading.text.lower()

    # Check dataset has description
    dataset_description = first_dataset.find("p", class_="usa-collection__description")
    assert dataset_description is not None


def test_htmx_search_uses_from_hint(interface_with_dataset, db_client):
    """
    Test that HTMX results have from_hint in dataset links
    """
    with patch("app.routes.interface", interface_with_dataset):
        # Simulate HTMX request with HX-Request header
        response = db_client.get(
            "/search",
            query_string={"q": "test", "per_page": "20", "from_hint": "badhint"},
            headers={"HX-Request": "true"},
        )
    soup = BeautifulSoup(response.text, "html.parser")

    dataset_items = soup.find_all("li", class_="usa-collection__item")
    assert all(
        "from_hint=badhint"
        in item.find("a", href=lambda href: href and "/dataset/" in href).get("href")
        for item in dataset_items
    )


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
    is only 11 datasets are returned based on the search so pagination shouldn't appear
    because it's less than the default 20
    """
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/organization/test-org?q=2016")

    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    dataset_section = soup.find("section", class_="organization-datasets")
    assert dataset_section is not None

    items = dataset_section.select(".usa-collection__item")
    assert len(items) == 11

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
    pagination occurs, the first page has 20 datasets (the search
    without pagination returns 47 datasets)

    """
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/organization/test-org?q=americorps&results=20")

    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    dataset_section = soup.find("section", class_="organization-datasets")
    assert dataset_section is not None

    items = dataset_section.select(".usa-collection__item")
    assert len(items) == 20

    # Check that show more results appears
    more_button = soup.find("button", class_="usa-button", attrs={"hx-get": True})
    assert more_button is not None


def test_organization_detail_displays_no_datasets_on_search(
    db_client, interface_with_dataset
):
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get(
            "/organization/test-org?q=nonexistenttermcompletelynothing"
        )

    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    dataset_section = soup.find("section", class_="organization-datasets")
    assert dataset_section is not None

    items = dataset_section.select(".usa-collection__item")
    assert len(items) == 0


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

    # Check sort has popularity option
    popularity_option = soup.find("option", {"value": "popularity"})
    assert popularity_option is not None

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
    response = db_client.get("/?q=climate&sort=relevance")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")

    # Check search input has the query value
    search_input = soup.find("input", {"name": "q"})
    assert search_input is not None
    assert search_input.get("value") == "climate"

    sort_input = soup.find("input", {"name": "sort", "type": "hidden"})
    assert sort_input is not None
    assert sort_input.get("value") == "relevance"


def test_index_page_popularity_sort_preserved(db_client):
    """Test that popularity sort selection is preserved between requests."""
    response = db_client.get("/?q=climate&per_page=10&sort=popularity")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")

    sort_select = soup.find("select", {"name": "sort", "id": "sort-select"})
    assert sort_select is not None

    popularity_option = sort_select.find("option", {"value": "popularity"})
    assert popularity_option is not None
    assert "selected" in popularity_option.attrs

    hidden_sort_input = soup.find("input", {"name": "sort", "type": "hidden"})
    assert hidden_sort_input is not None
    assert hidden_sort_input.get("value") == "popularity"


def test_index_page_lists_results_without_query(db_client):
    """Test that datasets render even when no query is provided."""
    mock_dataset = {
        "id": "mock-id",
        "slug": "mock-slug",
        "dcat": {
            "title": "Mock Dataset",
            "description": "Mock description",
            "distribution": [],
        },
        "organization": {
            "id": "org-id",
            "slug": "test-org",
            "name": "Test Org",
            "organization_type": "Federal Government",
        },
        "popularity": 42,
    }
    mock_result = SearchResult(total=1, results=[mock_dataset], search_after=None)
    mock_interface = Mock()
    mock_interface.search_datasets.return_value = mock_result
    mock_interface.get_unique_keywords.return_value = [
        {"keyword": "test", "count": 10},
        {"keyword": "data", "count": 5},
    ]
    mock_interface.total_datasets.return_value = 1

    with patch("app.routes.interface", mock_interface):
        response = db_client.get("/")

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    heading = soup.find("h3", class_="usa-collection__heading")
    assert heading is not None
    assert "Mock Dataset" in heading.text

    mock_interface.search_datasets.assert_called_once()


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
    assert "dataset" in results_text.text
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

    # dataset link should include a from_hint
    assert "from_hint=" in dataset_link.get("href")


def test_index_pagination_preserves_query_params(interface_with_dataset, db_client):
    """Test that pagination links preserve query and filter parameters."""
    # Create multiple datasets for pagination
    dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
    for i in range(25):
        dataset_dict["id"] = str(i)
        dataset_dict["slug"] = f"test-{i}"
        interface_with_dataset.db.add(Dataset(**dataset_dict))
    interface_with_dataset.db.commit()
    interface_with_dataset.opensearch.index_datasets(
        interface_with_dataset.db.query(Dataset)
    )

    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/?q=test&sort=relevance")

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    # Check that pagination links preserve parameters
    next_link = soup.find("button", class_="usa-button", attrs={"hx-get": True})
    href = next_link.get("hx-get")
    assert "q=test" in href
    assert "per_page=20" in href
    assert "sort=relevance" in href


def test_index_search_results_arg(interface_with_dataset, db_client):
    """Results controls how many results show up on the page."""
    # Create multiple datasets for pagination
    dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
    for i in range(25):
        dataset_dict["id"] = str(i)
        dataset_dict["slug"] = f"test-{i}"
        interface_with_dataset.db.add(Dataset(**dataset_dict))
    interface_with_dataset.db.commit()
    interface_with_dataset.opensearch.index_datasets(
        interface_with_dataset.db.query(Dataset)
    )

    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/?q=test&results=7")
    soup = BeautifulSoup(response.text, "html.parser")

    dataset_items = soup.find_all("li", class_="usa-collection__item")
    assert len(dataset_items) == 7


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


def test_index_from_hint_roundtrip(db_client, interface_with_dataset):
    # load a search results page with query parameters
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get("/?q=test&results=7")
    # find a dataset link
    soup = BeautifulSoup(response.text, "html.parser")
    dataset_link = soup.find("li", class_="usa-collection__item").find(
        "a", href=lambda href: "/dataset/" in href
    )
    # now open the dataset details link
    assert "from_hint=" in dataset_link.get("href")
    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get(dataset_link.get("href"))
    # and check to make sure that the return to search link has those same
    # query parameters
    soup = BeautifulSoup(response.text, "html.parser")
    return_link = soup.find("a", class_="return-link")
    assert return_link is not None
    assert "?q=test&results=7" in return_link.get("href")


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
    assert len(nav_parts) == 5  # “Data”, “Metrics”, “Organizations”, "Contact" “User Guide”

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


class TestKeywordSearch:
    """Test keyword search functionality on index page."""

    def test_single_keyword_filter_shows_matching_datasets(
        self, interface_with_dataset, db_client
    ):
        """Test filtering by a single keyword returns matching datasets."""
        dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
        for i in range(2):
            dataset_dict["id"] = str(i)
            dataset_dict["slug"] = f"test-{i}"
            dataset_dict["dcat"]["title"] = f"test-{i}"
            dataset_dict["dcat"]["keyword"] =["health", "education"]
            interface_with_dataset.db.add(Dataset(**dataset_dict))
        interface_with_dataset.db.commit()

        # Index datasets in OpenSearch
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )
        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get("/?keyword=health")

        assert response.status_code == 200
        soup = BeautifulSoup(response.text, "html.parser")

        # Verify at least one dataset is returned
        dataset_items = soup.find_all("li", class_="usa-collection__item")
        assert len(dataset_items) > 0

    def test_multiple_keywords_filter_shows_matching_datasets(
        self, interface_with_dataset, db_client
    ):
        """Test filtering by multiple keywords returns datasets with all keywords."""
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )

        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get("/?keyword=health&keyword=education")

        assert response.status_code == 200
        soup = BeautifulSoup(response.text, "html.parser")

        results_text = soup.find("p", class_="text-base-dark")
        assert results_text is not None

        # Verify at least one dataset is returned
        dataset_items = soup.find_all("li", class_="usa-collection__item")
        assert len(dataset_items) > 0

    def test_nonexistent_keyword_returns_no_results(
        self, interface_with_dataset, db_client
    ):
        """Test that filtering by a non-existent keyword returns no results."""
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )

        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get("/?keyword=nonexistentkeyword")

        assert response.status_code == 200
        soup = BeautifulSoup(response.text, "html.parser")

        # Check for no results message
        no_results_alert = soup.find("p", class_="usa-alert__text")
        assert no_results_alert is not None
        assert "No datasets found" in no_results_alert.text


class TestGeospatialSearch:
    """Test geospatial search functionality on index page."""

    def test_geospatial_filter_shows_only_spatial_datasets(
        self, interface_with_dataset, db_client
    ):
        """Test that geospatial filter returns only datasets with spatial data."""
        # Add spatial data to test dataset
        ds = interface_with_dataset.get_dataset_by_slug("test")
        ds.dcat["spatial"] = "-90.155,27.155,-90.26,27.255"
        interface_with_dataset.db.commit()

        # Index datasets in OpenSearch
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )

        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get("/?spatial_filter=geospatial")

        assert response.status_code == 200
        soup = BeautifulSoup(response.text, "html.parser")

        # Check that geospatial radio button is selected
        geo_radio = soup.find("input", {"id": "filter-spatial-geo"})
        assert geo_radio is not None
        assert "checked" in geo_radio.attrs

        # Verify results are displayed
        dataset_items = soup.find_all("li", class_="usa-collection__item")
        assert len(dataset_items) > 0

    def test_non_geospatial_filter_shows_only_non_spatial_datasets(
        self, interface_with_dataset, db_client
    ):
        """Test that non-geospatial filter returns only datasets without spatial data."""
        # Ensure test dataset has no spatial data
        ds = interface_with_dataset.get_dataset_by_slug("test")
        ds.dcat.pop("spatial", None)
        interface_with_dataset.db.commit()

        # Index datasets in OpenSearch
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )

        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get("/?spatial_filter=non-geospatial")

        assert response.status_code == 200
        soup = BeautifulSoup(response.text, "html.parser")

        # Check that non-geospatial radio button is selected
        non_geo_radio = soup.find("input", {"id": "filter-spatial-non-geo"})
        assert non_geo_radio is not None
        assert "checked" in non_geo_radio.attrs

        # Verify results are displayed
        dataset_items = soup.find_all("li", class_="usa-collection__item")
        assert len(dataset_items) > 0


def test_htmx_load_more_preserves_filters(interface_with_dataset, db_client):
    """Test that HTMX 'Show more results' button preserves all filter parameters."""
    # Create enough datasets to trigger pagination
    dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
    for i in range(30):
        dataset_dict["id"] = str(i)
        dataset_dict["slug"] = f"test-{i}"
        dataset_dict["dcat"]["title"] = f"test-{i}"
        dataset_dict["dcat"]["keyword"] =["health", "education"]
        dataset_dict["dcat"]["spatial"] = "-90.155,27.155,-90.26,27.255"
        interface_with_dataset.db.add(Dataset(**dataset_dict))
    interface_with_dataset.db.commit()

    # Index datasets in OpenSearch
    interface_with_dataset.opensearch.index_datasets(
        interface_with_dataset.db.query(Dataset)
    )

    with patch("app.routes.interface", interface_with_dataset):
        # Initial search with filters
        response = db_client.get(
            "/search",
            query_string={
                "q": "test",
                "per_page": "10",
                "org_type": "Federal Government",
                "keyword": "health",
                "spatial_filter": "geospatial",
                "sort": "popularity",
            },
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    # Find the "Show more results" button
    load_more_button = soup.find(
        "button", string=lambda s: s and "Show more results" in s
    )
    assert load_more_button is not None

    # Verify the button's hx-get URL contains all filter parameters
    hx_get_url = load_more_button.get("hx-get")
    assert hx_get_url is not None

    # Parse the URL to check query parameters
    parsed = urlparse(hx_get_url)
    params = parse_qs(parsed.query)

    assert params.get("q") == ["test"]
    assert params.get("org_type") == ["Federal Government"]
    assert params.get("keyword") == ["health"]
    assert params.get("spatial_filter") == ["geospatial"]
    assert params.get("sort") == ["popularity"]
    assert "after" in params
    assert "results" in params

    # Verify the hx-push-url also preserves filters
    hx_push_url = load_more_button.get("hx-push-url")
    assert hx_push_url is not None

    parsed_push = urlparse(hx_push_url)
    push_params = parse_qs(parsed_push.query)

    assert push_params.get("q") == ["test"]
    assert push_params.get("org_type") == ["Federal Government"]
    assert push_params.get("keyword") == ["health"]


def test_htmx_load_more_with_multiple_keywords(interface_with_dataset, db_client):
    """Test that multiple keywords are preserved in the load more button."""
    dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
    for i in range(25):
        dataset_dict["id"] = str(i)
        dataset_dict["slug"] = f"test-{i}"
        dataset_dict["dcat"] = {
            "title": f"test-{i}",
            "keyword": ["health", "education", "employment"],
        }
        interface_with_dataset.db.add(Dataset(**dataset_dict))
    interface_with_dataset.db.commit()

    interface_with_dataset.opensearch.index_datasets(
        interface_with_dataset.db.query(Dataset)
    )

    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get(
            "/search",
            query_string={
                "q": "test",
                "per_page": "10",
                "keyword": ["health", "education"],
            },
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    load_more_button = soup.find(
        "button", string=lambda s: s and "Show more results" in s
    )
    assert load_more_button is not None

    hx_get_url = load_more_button.get("hx-get")
    parsed = urlparse(hx_get_url)
    params = parse_qs(parsed.query)

    # Verify both keywords are present
    assert set(params.get("keyword", [])) == {"health", "education"}


def test_htmx_load_more_with_multiple_org_types(interface_with_dataset, db_client):
    """Test that multiple organization types are preserved in the load more button."""
    dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
    for i in range(25):
        dataset_dict["id"] = str(i)
        dataset_dict["slug"] = f"test-{i}"
        interface_with_dataset.db.add(Dataset(**dataset_dict))
    interface_with_dataset.db.commit()

    interface_with_dataset.opensearch.index_datasets(
        interface_with_dataset.db.query(Dataset)
    )

    with patch("app.routes.interface", interface_with_dataset):
        response = db_client.get(
            "/search",
            query_string={
                "q": "test",
                "per_page": "10",
                "org_type": ["Federal Government", "State Government"],
            },
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    load_more_button = soup.find(
        "button", string=lambda s: s and "Show more results" in s
    )
    assert load_more_button is not None

    hx_get_url = load_more_button.get("hx-get")
    parsed = urlparse(hx_get_url)
    params = parse_qs(parsed.query)

    # Verify both org types are present
    assert set(params.get("org_type", [])) == {"Federal Government", "State Government"}
