import re

from playwright.sync_api import expect

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
    expect(page.locator("#search-results div.usa-alert div p")).to_have_text(
        re.compile(r"^\s*No datasets found. ")
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
    page.locator("#filter-spatial-geo").scroll_into_view_if_needed()
    expect(page.locator("#filter-spatial-geo")).to_be_visible()

    page.locator("#filter-spatial-geo").dispatch_event("click")
    # after the click, filter is applied and the number of matching datasets
    # is given
    expect(page.locator("#search-results div.usa-prose p:first-child")).to_have_text(
        re.compile(r"^Found 10 datasets matching filters\.")
    )


def test_geography_suggestions_z_index(page):
    """
    The geography suggestions box should have a higher z-index than
    the Leaflet control buttons so it renders on top.
    """
    page.goto("/")
    page.locator("#geography-input").click()
    page.locator("#geography-input").press_sequentially("Washington", delay=1000)
    expect(page.locator("#geography-suggestions")).to_be_visible()

    first_suggestion = page.locator("#geography-suggestions .keyword-suggestion").first
    expect(first_suggestion).to_be_visible(timeout=1000)
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
