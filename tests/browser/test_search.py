import re

from playwright.sync_api import expect

from tests.browser.filter_helpers import (
    check_org_type_checkbox,
    check_spatial_radio,
    expand_filter_section,
    geography_input,
    keyword_input,
    open_filter_sidebar,
    spatial_radio,
    wait_for_filtered_results,
)

"""Test basic pages using the browser."""


def test_search(page):
    page.goto("/")
    page.get_by_role("textbox", name="Search datasets").fill("payments")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator("#search-results div.usa-prose p:first-child")).to_contain_text(
        "Found 8 datasets matching "
    )


def test_search_empty(page):
    page.goto("/")
    page.get_by_role("textbox", name="Search datasets").fill(
        "this search phrase has no results in the test data"
    )
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator("#no-datasets-alert")).to_contain_text(
        re.compile(r"Found\s+0\s+datasets")
    )


def test_return_to_search_results(page):
    page.goto("/")
    page.get_by_role("textbox", name="Search datasets").fill("payments")
    page.get_by_role("button", name="Search", exact=True).click()
    # now click on the first result
    page.get_by_role(
        "link", name="Segal AmeriCorps Education Award Payments by State"
    ).click()
    # has a "Return to search results" link
    expect(page.get_by_role("heading", level=1)).to_have_text(
        "Segal AmeriCorps Education Award Payments by State"
    )
    expect(
        page.get_by_role("link", name="\uf060 Return to search results")
    ).to_be_visible()

    page.get_by_role("link", name="\uf060 Return to search results").click()
    # back on the search page with same number of results
    expect(page.locator("#search-results div.usa-prose p:first-child")).to_contain_text(
        "Found 8 datasets matching "
    )


def test_filter_geospatial_click(page):
    """Searching for geospatial datasets filter is auto-applied."""
    page.goto("/")
    # initial page gives the total number available
    expect(page.locator("#search-results div.usa-prose p:first-child")).to_have_text(
        re.compile(r"^\s*\d+\s+datasets available on ")
    )
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-spatial")
    geospatial_radio = spatial_radio(page, "Geospatial only")
    expect(geospatial_radio).to_be_visible()

    check_spatial_radio(page, "Geospatial only")
    # after the click, filter is applied and the number of matching datasets
    # is given
    expect(page.locator("#search-results div.usa-prose p:first-child")).to_contain_text(
        re.compile(r"^Found \d+ datasets matching filters\.", re.I)
    )


def test_keyword_autocomplete_finds_earth(page):
    """Typing a single-word keyword finds a matching suggestion and filters results."""
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-keywords")
    keyword_input(page).fill("earth")
    suggestion = page.locator(
        '#keyword-suggestions .keyword-suggestion[data-keyword="earth"]'
    )
    expect(suggestion).to_be_visible()
    suggestion.click()
    expect(page.locator("#search-results div.usa-prose p:first-child")).to_contain_text(
        "matching filters"
    )


def test_keyword_autocomplete_finds_earth_science(page):
    """Typing a multi-word keyword finds a matching suggestion and filters results."""
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-keywords")
    keyword_input(page).fill("earth science")
    suggestion = page.locator(
        '#keyword-suggestions .keyword-suggestion[data-keyword="earth science"]'
    )
    expect(suggestion).to_be_visible()
    suggestion.click()
    expect(page.locator("#search-results div.usa-prose p:first-child")).to_contain_text(
        "matching filters"
    )


def test_keyword_autocomplete_finds_earth_science_trees(page):
    """Typing a keyword containing '>' finds a matching suggestion and filters results."""
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-keywords")
    keyword_input(page).fill("earth science > trees")
    suggestion = page.locator(
        '#keyword-suggestions .keyword-suggestion[data-keyword="earth science > trees"]'
    )
    expect(suggestion).to_be_visible()
    suggestion.click()
    expect(page.locator("#search-results div.usa-prose p:first-child")).to_contain_text(
        "matching filters"
    )


def test_clear_all_filters_not_shown_for_query_without_filters(page):
    """
    A bare query with no active filters must not show "(clear all filters)"
    since there is nothing to clear.
    """
    page.goto("/")
    page.get_by_role("textbox", name="Search datasets").fill("payments")
    page.get_by_role("button", name="Search", exact=True).click()

    results_paragraph = page.locator("#search-results div.usa-prose p:first-child")
    expect(results_paragraph).to_contain_text('matching "payments"')
    expect(
        results_paragraph.get_by_role("link", name="(clear all filters)")
    ).not_to_be_visible()


def test_clear_all_filters_and_preserves_query(page):
    """
    When filters are active alongside a search query, clicking '(clear all
    filters)' strips the filters but keeps the original query in the results.
    """
    page.goto("/")
    page.get_by_role("textbox", name="Search datasets").fill("payments")
    page.get_by_role("button", name="Search", exact=True).click()

    open_filter_sidebar(page)
    expand_filter_section(page, "filter-organization")

    check_org_type_checkbox(page, "Federal Government")

    wait_for_filtered_results(page)

    results_paragraph = page.locator("#search-results div.usa-prose p:first-child")
    expect(results_paragraph).to_contain_text('"payments" and filters.')
    clear_link = results_paragraph.get_by_role("link", name="(clear all filters)")
    expect(clear_link).to_be_visible()

    clear_link.click()

    # Query is preserved; filters are gone.
    expect(results_paragraph).to_contain_text('matching "payments"')
    expect(
        results_paragraph.get_by_role("link", name="(clear all filters)")
    ).not_to_be_visible()


def test_geography_suggestions_z_index(page):
    """
    The geography suggestions box should have a higher z-index than
    the Leaflet control buttons so it renders on top.
    """
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-geography")
    geography_input(page).click()
    geography_input(page).fill("Washington")
    first_suggestion = page.locator("#geography-suggestions .keyword-suggestion").first
    expect(first_suggestion).to_be_visible()
    first_suggestion.scroll_into_view_if_needed()
    z_indices = page.evaluate("""() => {
        function effectiveZIndex(el) {
            while (el && el !== document.body) {
                const style = window.getComputedStyle(el);
                const z = style.zIndex;
                if (style.position !== "static" && z !== "auto") {
                    return parseInt(z, 10);
                }
                el = el.parentElement;
            }
            return 0;
        }
 
        return {
            suggestions: effectiveZIndex(
                document.getElementById("geography-suggestions")
            ),
            leaflet: effectiveZIndex(
                document.querySelector(".leaflet-top.leaflet-left")
            ),
        };
    }""")

    assert z_indices["suggestions"] > z_indices["leaflet"], (
        f"#geography-suggestions effective z-index ({z_indices['suggestions']}) "
        f"should be greater than .leaflet-top.leaflet-left ({z_indices['leaflet']})"
    )
