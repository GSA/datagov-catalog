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
    """Selecting the geospatial radio and pressing Apply filters the results."""
    page.goto("/")
    # initial page gives the total number available
    expect(page.locator("#search-results p.text-base-dark").first).to_have_text(
        re.compile(r"^\s*\d+\s+datasets available on ")
    )
    # open the Spatial Data dropdown, choose Geospatial only, then Apply.
    # USWDS visually hides the radio input off-screen, so click its label.
    page.locator("#filter-button-spatial").click()
    page.locator('label[for="filter-spatial-geo"]').click()
    page.locator('[data-filter-apply="spatial"]').click()
    # after Apply, the filter is reflected in the URL and the result count
    expect(page).to_have_url(re.compile(r"spatial_filter=geospatial"))
    expect(page.locator("#search-results p.text-base-dark").first).to_have_text(
        re.compile(r"^Found 18 datasets matching filters\.")
    )


def _apply_keyword_via_dropdown(page, keyword):
    """Open the Keywords dropdown, pick a suggestion, and press Apply."""
    page.locator("#filter-button-keywords").click()
    page.locator("#keyword-input").fill(keyword)
    suggestion = page.locator(
        f'#keyword-suggestions .keyword-suggestion[data-keyword="{keyword}"]'
    )
    expect(suggestion).to_be_visible()
    suggestion.click()
    page.locator('[data-filter-apply="keywords"]').click()


def test_keyword_autocomplete_finds_earth(page):
    """Typing a single-word keyword finds a matching suggestion and filters results."""
    page.goto("/")
    _apply_keyword_via_dropdown(page, "earth")
    expect(page.locator("#search-results p.text-base-dark").first).to_contain_text(
        "matching filters"
    )
    expect(page).to_have_url(re.compile(r"keyword=earth"))


def test_keyword_autocomplete_finds_earth_science(page):
    """Typing a multi-word keyword finds a matching suggestion and filters results."""
    page.goto("/")
    _apply_keyword_via_dropdown(page, "earth science")
    expect(page.locator("#search-results p.text-base-dark").first).to_contain_text(
        "matching filters"
    )


def test_keyword_autocomplete_finds_earth_science_trees(page):
    """Typing a keyword containing '>' finds a matching suggestion and filters results."""
    page.goto("/")
    _apply_keyword_via_dropdown(page, "earth science > trees")
    expect(page.locator("#search-results p.text-base-dark").first).to_contain_text(
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

    # Apply an org type filter on top of the query via the dropdown.
    # USWDS visually hides the checkbox input off-screen, so click its label.
    page.locator("#filter-button-org_type").click()
    page.locator('label[for="filter-federal"]').click()
    page.locator('[data-filter-apply="org_type"]').click()

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
    # open the Geographic Area dropdown
    page.locator("#filter-button-geography").click()
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


def test_geography_filter_returns_results(page):
    """Selecting a geography location filters datasets to that area."""
    page.goto("/")
    page.locator("#filter-button-geography").click()
    page.locator("#geography-input").fill("Oregon")
    suggestion = page.locator("#geography-suggestions .keyword-suggestion").first
    expect(suggestion).to_be_visible()
    suggestion.click()

    # Selecting a location applies immediately and narrows the results.
    expect(page).to_have_url(re.compile(r"spatial_geometry="))
    expect(page.locator("#search-results p.text-base-dark").first).to_contain_text(
        "matching filters"
    )


def test_geography_map_tiles_load(page):
    """The Leaflet map renders OpenStreetMap tiles (served via /maptiles)."""
    page.goto("/")
    page.locator("#filter-button-geography").click()
    page.locator("#geography-input").fill("Oregon")
    suggestion = page.locator("#geography-suggestions .keyword-suggestion").first
    expect(suggestion).to_be_visible()
    suggestion.click()

    # At least one map tile image should load successfully.
    tile = page.locator("img.leaflet-tile").first
    expect(tile).to_be_visible()
    tile_count = page.evaluate(
        "() => document.querySelectorAll('img.leaflet-tile').length"
    )
    assert tile_count > 0


def test_filter_dropdown_opens_and_closes(page):
    """A facet button toggles its panel and tracks aria-expanded state."""
    page.goto("/")
    button = page.locator("#filter-button-keywords")
    panel = page.locator("#filter-panel-keywords")

    expect(panel).to_be_hidden()
    expect(button).to_have_attribute("aria-expanded", "false")

    button.click()
    expect(panel).to_be_visible()
    expect(button).to_have_attribute("aria-expanded", "true")

    # Escape closes the panel and restores focus to the button.
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()
    expect(button).to_have_attribute("aria-expanded", "false")
    expect(button).to_be_focused()


def test_filter_dropdown_closes_on_outside_click(page):
    """Clicking outside an open panel closes it."""
    page.goto("/")
    page.locator("#filter-button-spatial").click()
    expect(page.locator("#filter-panel-spatial")).to_be_visible()

    page.locator("#search-query").click()
    expect(page.locator("#filter-panel-spatial")).to_be_hidden()


def test_filter_deferred_until_apply(page):
    """Staging a selection does not change results until Apply is pressed."""
    page.goto("/")
    page.locator("#filter-button-spatial").click()
    page.locator('label[for="filter-spatial-geo"]').click()

    # Still on the unfiltered homepage — no submit yet.
    expect(page).not_to_have_url(re.compile(r"spatial_filter=geospatial"))

    page.locator('[data-filter-apply="spatial"]').click()
    expect(page).to_have_url(re.compile(r"spatial_filter=geospatial"))


def test_filter_badge_appears_after_apply(page):
    """Applying a filter shows a count badge on its facet button."""
    page.goto("/")
    badge = page.locator('[data-filter-badge="spatial"]')
    expect(badge).to_be_hidden()

    page.locator("#filter-button-spatial").click()
    page.locator('label[for="filter-spatial-geo"]').click()
    page.locator('[data-filter-apply="spatial"]').click()

    expect(badge).to_be_visible()
    expect(badge).to_have_text("1")


def test_chip_remove_auto_applies(page):
    """Clicking a chip's "x" removes that filter and applies immediately."""
    # Start with an active keyword filter.
    page.goto("/?keyword=health")
    expect(page).to_have_url(re.compile(r"keyword=health"))
    expect(page.locator('[data-filter-badge="keywords"]')).to_be_visible()

    # Open the keyword panel and remove the chip via its "x".
    page.locator("#filter-button-keywords").click()
    page.locator("#keyword-chips .keyword-chip__remove").first.click()

    # The removal is applied without needing to press Apply.
    expect(page).not_to_have_url(re.compile(r"keyword=health"))
    expect(page.locator('[data-filter-badge="keywords"]')).to_be_hidden()


def test_publisher_combo_clear_auto_applies(page):
    """Clearing the publisher combo box (USWDS × button) applies immediately."""
    page.goto("/?publisher=AmeriCorps")
    expect(page).to_have_url(re.compile(r"publisher=AmeriCorps"))

    page.locator("#filter-button-publisher").click()
    # USWDS combo box renders a clear ("×") button when a value is selected.
    page.locator(
        '.usa-combo-box[data-filter-combo="publisher"] .usa-combo-box__clear-input'
    ).click()

    expect(page).not_to_have_url(re.compile(r"publisher=AmeriCorps"))


def test_filter_panel_clear_resets_filter(page):
    """The per-panel Clear action removes that filter and re-runs the search."""
    # Start with an active spatial filter.
    page.goto("/?spatial_filter=geospatial")
    expect(page.locator('[data-filter-badge="spatial"]')).to_be_visible()

    page.locator("#filter-button-spatial").click()
    page.locator('[data-filter-clear="spatial"]').click()

    # Filter is gone from the URL and the badge disappears.
    expect(page).not_to_have_url(re.compile(r"spatial_filter=geospatial"))
    expect(page.locator('[data-filter-badge="spatial"]')).to_be_hidden()


def test_filter_persists_in_query_string_on_reload(page):
    """An applied filter survives a page reload via the query string."""
    page.goto("/")
    page.locator("#filter-button-spatial").click()
    page.locator('label[for="filter-spatial-geo"]').click()
    page.locator('[data-filter-apply="spatial"]').click()
    expect(page).to_have_url(re.compile(r"spatial_filter=geospatial"))

    page.reload()
    # The control reflects the persisted state and the badge is shown.
    expect(page.locator("#filter-button-spatial")).to_be_visible()
    page.locator("#filter-button-spatial").click()
    expect(page.locator("#filter-spatial-geo")).to_be_checked()
    expect(page.locator('[data-filter-badge="spatial"]')).to_have_text("1")


def test_sort_change_preserves_active_filter(page):
    """Changing sort keeps the active filter in the query string."""
    page.goto("/?spatial_filter=geospatial")
    page.locator("#sort-select").select_option("popularity")
    expect(page).to_have_url(re.compile(r"spatial_filter=geospatial"))
    expect(page).to_have_url(re.compile(r"sort=popularity"))


def test_filters_open_as_bottom_drawer_on_mobile(page):
    """On a narrow viewport the panel renders as a bottom drawer with a header."""
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto("/")

    page.locator("#filter-button-spatial").click()
    panel = page.locator("#filter-panel-spatial")
    expect(panel).to_be_visible()
    # The drawer header (close button) is only shown in the mobile layout.
    expect(panel.locator('[data-filter-close="spatial"]')).to_be_visible()
    # Backdrop is shown behind the drawer.
    expect(page.locator("[data-filter-backdrop]")).to_be_visible()

    # The panel is anchored to the bottom of the viewport.
    box = panel.bounding_box()
    assert box["y"] + box["height"] >= 667 - 2

    # Tapping the backdrop closes the drawer.
    page.locator("[data-filter-backdrop]").click(position={"x": 10, "y": 10})
    expect(panel).to_be_hidden()


def test_badge_does_not_change_while_staging(page):
    """Staging selections must not change the facet badge until Apply."""
    page.goto("/")
    badge = page.locator('[data-filter-badge="org_type"]')
    expect(badge).to_be_hidden()

    page.locator("#filter-button-org_type").click()
    page.locator('label[for="filter-federal"]').click()
    page.locator('label[for="filter-state"]').click()

    # Still hidden: the badge reflects only applied state, not staged checkboxes.
    expect(badge).to_be_hidden()

    page.locator('[data-filter-apply="org_type"]').click()
    expect(badge).to_have_text("2")


def test_keyword_enter_applies_filter(page):
    """Pressing Enter in the keyword input applies the top suggestion."""
    page.goto("/")
    page.locator("#filter-button-keywords").click()
    page.locator("#keyword-input").fill("earth")
    expect(
        page.locator('#keyword-suggestions .keyword-suggestion[data-keyword="earth"]')
    ).to_be_visible()
    page.locator("#keyword-input").press("Enter")

    expect(page).to_have_url(re.compile(r"keyword=earth"))
    expect(page.locator("#search-results p.text-base-dark").first).to_contain_text(
        "matching filters"
    )


def _combo_pick(page, facet, typed):
    """Type into a USWDS combo box and click the first matching option."""
    combo = f'.usa-combo-box[data-filter-combo="{facet}"]'
    page.locator(f"{combo} input.usa-combo-box__input").fill(typed)
    option = page.locator(f'{combo} li[role="option"]').first
    expect(option).to_be_visible()
    option.click()


def test_organization_select_auto_applies(page):
    """Organization is single-select: choosing from the combo box auto-applies."""
    page.goto("/")
    panel = page.locator("#filter-panel-organization")
    # Single-select facets have no Apply/Clear footer.
    expect(panel.locator('[data-filter-apply="organization"]')).to_have_count(0)

    page.locator("#filter-button-organization").click()
    _combo_pick(page, "organization", "Portland")

    # Applied without pressing Apply.
    expect(page).to_have_url(re.compile(r"org_slug=city-of-portland"))
    expect(page.locator("#search-results p.text-base-dark").first).to_contain_text(
        "matching filters"
    )


def test_publisher_select_auto_applies(page):
    """Publisher is single-select: choosing from the combo box auto-applies."""
    page.goto("/")
    panel = page.locator("#filter-panel-publisher")
    expect(panel.locator('[data-filter-apply="publisher"]')).to_have_count(0)

    page.locator("#filter-button-publisher").click()
    _combo_pick(page, "publisher", "americorps")

    expect(page).to_have_url(re.compile(r"publisher="))
    expect(page.locator("#search-results p.text-base-dark").first).to_contain_text(
        "matching filters"
    )


def test_zero_results_clear_all_filters_link(page):
    """The no-results view exposes a working (clear all filters) link."""
    page.goto("/?q=zzzznomatchatall&spatial_filter=geospatial")
    alert = page.locator("#no-datasets-alert")
    expect(alert).to_be_visible()
    clear_link = alert.get_by_role("link", name="(clear all filters)")
    expect(clear_link).to_be_visible()

    clear_link.click()
    expect(page).not_to_have_url(re.compile(r"spatial_filter=geospatial"))
