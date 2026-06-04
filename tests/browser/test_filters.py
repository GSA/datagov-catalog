"""Playwright tests that verify catalog filters change search results.

These tests require the demo filter fixture data loaded into the running app
(for example via ``make test-browser-with-data``).
"""

from playwright.sync_api import Page, expect

from tests.browser.filter_helpers import (
    check_org_type_checkbox,
    check_spatial_radio,
    expand_filter_section,
    expect_result_hidden,
    expect_result_visible,
    geography_input,
    keyword_input,
    open_filter_sidebar,
    organization_input,
    publisher_input,
    sort_select,
    wait_for_filtered_results,
)


def test_keyword_filter_limits_results(page: Page) -> None:
    """Selecting a keyword shows matching datasets and hides unrelated ones."""
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-keywords")
    keyword_input(page).fill("wildfire")
    suggestion = page.locator(
        '#keyword-suggestions .keyword-suggestion[data-keyword="wildfire"]'
    )
    expect(suggestion).to_be_visible()
    suggestion.click()

    wait_for_filtered_results(page)
    expect_result_visible(page, "California Wildfire Perimeters")
    expect_result_hidden(page, "Portland Bike Lane Network")


def test_publisher_filter_limits_results(page: Page) -> None:
    """Selecting a publisher shows only datasets from that publisher."""
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-publishers")
    publisher_input(page).fill("Portland Bureau")
    suggestion = page.locator(
        '#publisher-suggestions .keyword-suggestion[data-publisher-name="Portland Bureau of Transportation"]'
    )
    expect(suggestion).to_be_visible()
    suggestion.click()

    wait_for_filtered_results(page)
    expect_result_visible(page, "Portland Bike Lane Network")
    expect_result_hidden(page, "California Wildfire Perimeters")


def test_organization_filter_limits_results(page: Page) -> None:
    """Selecting an organization shows only datasets published by that org."""
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-organization-autocomplete")
    organization_input(page).fill("City of Portland")
    suggestion = page.locator(
        '#organization-suggestions .keyword-suggestion[data-org-slug="city-of-portland"]'
    )
    expect(suggestion).to_be_visible()
    suggestion.click()

    wait_for_filtered_results(page)
    expect_result_visible(page, "Portland Bike Lane Network")
    expect_result_visible(page, "Portland Park Tree Inventory")
    expect_result_hidden(page, "California Wildfire Perimeters")


def test_organization_type_filter_limits_results(page: Page) -> None:
    """Organization type checkboxes restrict results to matching org categories."""
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-organization")

    check_org_type_checkbox(page, "City Government")

    wait_for_filtered_results(page)
    expect_result_visible(page, "Portland Bike Lane Network")
    expect_result_hidden(page, "California Wildfire Perimeters")


def test_geography_map_fills_container_after_accordion_expand(page: Page) -> None:
    """The sidebar map should size correctly after expanding a collapsed section."""
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-geography")

    map_size = page.evaluate("""() => {
            const controller = window.dataGovGeographyAutocomplete;
            const map = controller && controller.map;
            if (!map || typeof map.getSize !== 'function') {
                return null;
            }
            const size = map.getSize();
            return { x: size.x, y: size.y };
        }""")
    assert map_size is not None
    assert map_size["x"] >= 200
    assert map_size["y"] >= 150


def test_geography_filter_limits_results(page: Page) -> None:
    """Selecting a geography suggestion limits results to datasets in that area."""
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-geography")
    geography_input(page).fill("Portland")
    suggestion = page.locator(
        "#geography-suggestions .keyword-suggestion",
        has_text="Portland, Oregon",
    )
    expect(suggestion).to_be_visible()
    suggestion.click()

    wait_for_filtered_results(page)
    expect_result_visible(page, "Portland Bike Lane Network")
    expect_result_hidden(page, "California Wildfire Perimeters")


def test_geospatial_filter_limits_results(page: Page) -> None:
    """The geospatial-only radio hides datasets without spatial data."""
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-spatial")

    check_spatial_radio(page, "Geospatial only")

    wait_for_filtered_results(page)
    expect_result_visible(page, "Portland Bike Lane Network")
    expect_result_hidden(page, "University of Michigan Research Grants")


def test_non_geospatial_filter_limits_results(page: Page) -> None:
    """The non-geospatial radio hides datasets that have spatial data."""
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-spatial")

    check_spatial_radio(page, "Non-geospatial only")

    wait_for_filtered_results(page)
    expect_result_visible(page, "University of Michigan Research Grants")
    expect_result_hidden(page, "Portland Bike Lane Network")


def test_sort_by_popularity_preserves_active_filters(page: Page) -> None:
    """Popularity sort preserves keyword filters in the URL, UI, and results."""
    page.goto("/?keyword=health&sort=popularity")
    wait_for_filtered_results(page)
    expect(sort_select(page)).to_have_value("popularity")
    expect(page.locator("#keyword-chips .tag-link")).to_contain_text("health")
    expect_result_visible(page, "Red Cross Blood Drive Schedule")


def test_sort_select_syncs_hidden_filter_form_input(page: Page) -> None:
    """Changing the sort dropdown updates the hidden sort field before submit."""
    page.goto("/?keyword=health")
    wait_for_filtered_results(page)
    open_filter_sidebar(page)

    sort_select(page).select_option("popularity")

    expect(
        page.locator('#filter-form input[name="sort"][type="hidden"]')
    ).to_have_value("popularity")
