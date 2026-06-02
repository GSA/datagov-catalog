"""Browser tests that verify sort order and filter behavior actually take
effect in the rendered results — not just that the URL/query string changes.

The existing ``test_search.py`` suite covers the filter *mechanics* (dropdowns,
badges, chips, apply/clear, URL persistence) and a couple of result counts.
These tests close the remaining gap: they assert that

* each sort option actually orders the visible results, and changing the sort
  control re-orders what the user sees, and
* each filter actually constrains the visible results to matching datasets.

They rely on the seeded demo fixtures in ``tests/fixtures.py`` (loaded via
``make ... load-test-data``), whose popularity values, harvest dates, and
spatial extents are deterministic.
"""

import re

from playwright.sync_api import expect

# Card metrics render as "... | Views last month: N | Catalog Last Checked: ..."
# inside <small class="text-base-dark"> on each result card.
_METRIC = "#search-results small.text-base-dark"


def _result_titles(page):
    """Visible dataset titles, in order, from the result cards."""
    return page.locator("#search-results .usa-collection__heading a").all_inner_texts()


def _view_counts(page):
    """The 'Views last month: N' value from each result card, in order."""
    texts = page.locator(_METRIC).all_inner_texts()
    counts = []
    for text in texts:
        match = re.search(r"Views last month:\s*(\d+)", text)
        if match:
            counts.append(int(match.group(1)))
    return counts


def _is_descending(values):
    return all(earlier >= later for earlier, later in zip(values, values[1:]))


def _is_ascending(values):
    return all(earlier <= later for earlier, later in zip(values, values[1:]))


# --------------------------------------------------------------------------- #
# Sort order
# --------------------------------------------------------------------------- #


def test_popularity_sort_orders_results_descending(page):
    """Popularity sort renders results in descending 'Views last month' order."""
    page.goto("/?sort=popularity")
    expect(page.locator("#sort-select")).to_have_value("popularity")

    counts = _view_counts(page)
    assert len(counts) >= 5, f"expected several cards with view counts, got {counts}"
    assert _is_descending(counts), f"view counts not descending: {counts}"


def test_changing_sort_control_reorders_visible_results(page):
    """Switching the sort <select> from relevance to popularity actually
    re-orders the results the user sees.

    For the seeded 'health' query the relevance order is intentionally NOT
    sorted by popularity (high-popularity datasets are interleaved with more
    textually-relevant ones), so the view-count sequence is non-monotonic under
    relevance but becomes strictly descending under popularity. That difference
    is what proves the sort took effect on the rendered page.
    """
    page.goto("/")
    page.get_by_role("textbox", name="Search datasets").fill("health")
    page.get_by_role("button", name="Search", exact=True).click()

    expect(page.locator("#sort-select")).to_have_value("relevance")
    relevance_counts = _view_counts(page)
    assert len(relevance_counts) >= 5
    # Relevance ordering for this query is not popularity-descending.
    assert not _is_descending(
        relevance_counts
    ), f"relevance order unexpectedly descending by views: {relevance_counts}"

    # Changing the sort control submits the search form and re-runs the query.
    page.locator("#sort-select").select_option("popularity")
    expect(page).to_have_url(re.compile(r"sort=popularity"))
    expect(page).to_have_url(re.compile(r"q=health"))

    popularity_counts = _view_counts(page)
    assert len(popularity_counts) >= 5
    assert _is_descending(
        popularity_counts
    ), f"after switching to popularity, views not descending: {popularity_counts}"
    # The order genuinely changed (not just the query string).
    assert popularity_counts != relevance_counts


def test_last_harvested_date_sort_orders_results_newest_first(page):
    """Last-published-date sort renders 'Catalog Last Checked' newest first."""
    page.goto("/?sort=last_harvested_date")
    expect(page.locator("#sort-select")).to_have_value("last_harvested_date")

    # The check timestamps are rendered as human dates; parse them back and
    # assert the seeded data lists the most recently-checked datasets first.
    checked = [
        match.group(1)
        for line in page.locator(_METRIC).all_inner_texts()
        for match in [re.search(r"Catalog Last Checked:\s*(.+?)\s*$", line)]
        if match
    ]
    assert len(checked) >= 5, f"expected dated cards, got {checked}"

    parsed = [_parse_checked_date(text) for text in checked]
    assert all(d is not None for d in parsed), f"unparseable dates: {checked}"
    assert _is_descending(parsed), f"harvest dates not newest-first: {checked}"


def _parse_checked_date(text):
    """Parse 'Month DD, YYYY at HH:MM AM/PM' into a comparable datetime."""
    from datetime import datetime

    for fmt in ("%B %d, %Y at %I:%M %p", "%B %d, %Y"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def test_distance_sort_orders_results_nearest_first(page):
    """After choosing a geography, Distance sort orders results nearest-first.

    Distance is only selectable once a geographic area is chosen (otherwise the
    option is disabled), so this also exercises the geography -> distance flow.
    """
    page.goto("/")

    # Choose the seeded "Oregon" location from the geography autocomplete.
    page.locator("#filter-button-geography").click()
    page.locator("#geography-input").fill("Oregon")
    suggestion = page.locator(
        "#geography-suggestions .keyword-suggestion", has_text="Oregon"
    ).first
    expect(suggestion).to_be_visible()
    suggestion.click()
    page.locator('[data-filter-apply="geography"]').click()

    # Geography is deferred: stage the selection, then Apply.
    expect(page).to_have_url(re.compile(r"spatial_geometry="))
    expect(page.locator('#sort-select option[value="distance"]')).not_to_have_attribute(
        "disabled", "disabled"
    )

    page.locator("#sort-select").select_option("distance")
    expect(page).to_have_url(re.compile(r"sort=distance"))
    # Geography is preserved across the sort change.
    expect(page).to_have_url(re.compile(r"spatial_geometry="))

    distances = []
    for text in page.locator(_METRIC).all_inner_texts():
        match = re.search(r"Distance:\s*([\d.]+)\s*mi", text)
        if match:
            distances.append(float(match.group(1)))

    assert len(distances) >= 2, f"expected >=2 cards with distances, got {distances}"
    assert _is_ascending(distances), f"distances not nearest-first: {distances}"


# --------------------------------------------------------------------------- #
# Filters actually constrain the results
# --------------------------------------------------------------------------- #


def test_keyword_filter_limits_results_to_matching_dataset(page):
    """The keyword filter returns only datasets tagged with that keyword.

    'trees' is seeded on exactly one demo dataset.
    """
    page.goto("/?keyword=trees")
    expect(page.locator("#search-results p.text-base-dark").first).to_contain_text(
        re.compile(r"Found 1 dataset matching filters\.")
    )
    assert _result_titles(page) == ["Portland Park Tree Inventory"]


def test_organization_type_filter_limits_results_to_that_type(page):
    """Filtering by an org type shows only datasets from that government type.

    The two demo 'City of Portland' datasets are the only City Government rows.
    """
    page.goto("/")
    page.locator("#filter-button-org_type").click()
    page.locator('label[for="filter-city"]').click()
    page.locator('[data-filter-apply="org_type"]').click()

    expect(page).to_have_url(re.compile(r"org_type=City\+Government"))
    expect(page.locator("#search-results p.text-base-dark").first).to_contain_text(
        "Found 2 datasets matching filters."
    )
    # Every card's org-type banner reads "City".
    banner_types = page.locator(
        "#search-results .dataset-org-banner__type"
    ).all_inner_texts()
    assert banner_types, "expected org-type banners on result cards"
    assert all(bt.strip() == "City" for bt in banner_types), banner_types
    assert sorted(_result_titles(page)) == [
        "Portland Bike Lane Network",
        "Portland Park Tree Inventory",
    ]


def test_organization_filter_limits_results_to_that_org(page):
    """Selecting an organization shows only that organization's datasets."""
    page.goto("/")
    page.locator("#filter-button-organization").click()
    combo = '.usa-combo-box[data-filter-combo="organization"]'
    page.locator(f"{combo} input.usa-combo-box__input").fill("Portland")
    option = page.locator(f'{combo} li[role="option"]').first
    expect(option).to_be_visible()
    option.click()
    # Organization is deferred: stage the selection, then Apply.
    page.locator('[data-filter-apply="organization"]').click()

    expect(page).to_have_url(re.compile(r"org_slug=city-of-portland"))
    expect(page.locator("#search-results p.text-base-dark").first).to_contain_text(
        "Found 2 datasets matching filters."
    )
    assert sorted(_result_titles(page)) == [
        "Portland Bike Lane Network",
        "Portland Park Tree Inventory",
    ]


def test_publisher_filter_limits_results_to_that_publisher(page):
    """Selecting a publisher shows only that publisher's datasets."""
    page.goto("/")
    page.locator("#filter-button-publisher").click()
    combo = '.usa-combo-box[data-filter-combo="publisher"]'
    page.locator(f"{combo} input.usa-combo-box__input").fill("American Red Cross")
    option = page.locator(f'{combo} li[role="option"]').first
    expect(option).to_be_visible()
    option.click()
    # Publisher is deferred: stage the selection, then Apply.
    page.locator('[data-filter-apply="publisher"]').click()

    expect(page).to_have_url(re.compile(r"publisher=American\+Red\+Cross"))
    expect(page.locator("#search-results p.text-base-dark").first).to_contain_text(
        "Found 2 datasets matching filters."
    )
    assert sorted(_result_titles(page)) == [
        "Red Cross Blood Drive Schedule",
        "Red Cross Shelter Locations",
    ]


def test_spatial_data_filter_limits_results(page):
    """The 'Geospatial' spatial-data filter narrows the result count."""
    page.goto("/")
    # Baseline: homepage shows the available-datasets count.
    expect(page.locator("#search-results p.text-base-dark").first).to_have_text(
        re.compile(r"^\s*\d+\s+datasets available on ")
    )

    page.locator("#filter-button-spatial").click()
    page.locator('label[for="filter-spatial-geo"]').click()
    page.locator('[data-filter-apply="spatial"]').click()

    expect(page).to_have_url(re.compile(r"spatial_filter=geospatial"))
    expect(page.locator("#search-results p.text-base-dark").first).to_have_text(
        re.compile(r"^Found 18 datasets matching filters\.")
    )


def test_geography_filter_limits_results_to_area(page):
    """Selecting a geographic area shows only datasets within that area.

    The seeded 'Oregon' extent covers exactly the two Portland demo datasets.
    """
    page.goto("/")
    page.locator("#filter-button-geography").click()
    page.locator("#geography-input").fill("Oregon")
    suggestion = page.locator(
        "#geography-suggestions .keyword-suggestion", has_text="Oregon"
    ).first
    expect(suggestion).to_be_visible()
    suggestion.click()
    page.locator('[data-filter-apply="geography"]').click()

    expect(page).to_have_url(re.compile(r"spatial_geometry="))
    expect(page.locator("#search-results p.text-base-dark").first).to_contain_text(
        "matching filters"
    )
    assert sorted(_result_titles(page)) == [
        "Portland Bike Lane Network",
        "Portland Park Tree Inventory",
    ]


def test_geography_filter_restores_place_name_after_apply(page):
    """Reopening the geography facet after Apply shows the selected place name."""
    page.goto("/")
    page.locator("#filter-button-geography").click()
    page.locator("#geography-input").fill("Oregon")
    suggestion = page.locator(
        "#geography-suggestions .keyword-suggestion", has_text="Oregon"
    ).first
    expect(suggestion).to_be_visible()
    suggestion.click()
    page.locator('[data-filter-apply="geography"]').click()

    expect(page).to_have_url(re.compile(r"spatial_geometry="))
    expect(page).to_have_url(re.compile(r"spatial_label=Oregon"))

    page.locator("#filter-button-geography").click()
    expect(page.locator("#geography-input")).to_have_value("Oregon")
