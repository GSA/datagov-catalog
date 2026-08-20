"""Test organization list and organization detail pages."""

import re

from playwright.sync_api import expect

from tests.browser.filter_helpers import (
    expand_filter_section,
    keyword_input,
    open_filter_sidebar,
)


def test_organization_list(page):
    page.goto("/organization")
    expect(page.get_by_role("heading", name="test org")).to_be_visible()


def test_organization_detail(page):
    page.goto("/organization/test-org")
    # title
    expect(page.get_by_role("heading", level=1)).to_have_text("test org")
    # dataset total
    expect(page.locator("li.usa-summary-box__item").nth(1)).to_have_text(
        re.compile(r"Total datasets: \d+")
    )


def test_organization_detail_keyword_click(page):
    page.goto("/organization/test-org")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-keywords")
    keyword_input(page).fill("health")
    suggestion = page.locator(
        '#keyword-suggestions .keyword-suggestion[data-keyword="health"]'
    )
    expect(suggestion).to_be_visible()
    suggestion.click()

    expect(
        page.get_by_role("paragraph").filter(has_text="datasets matching")
    ).to_have_text(re.compile(r"matching\s+filters", re.I))


def test_organization_detail_return_to_search_results(page, base_url):
    page.goto("/organization/test-org")

    # submit query and wait for the results navigation to complete
    page.locator("#search-query").fill("2020")
    with page.expect_navigation(url=re.compile(r"\?q=2020")):
        page.locator("#main-search-form").get_by_role("button", name="Search").click()

    # wait for the search results page to load before reading dataset links;
    # otherwise we may grab a link from the pre-search page (which lacks the
    # from_hint needed to render the "Return to search results" link)
    page.wait_for_url(re.compile(r"[?&]q=2020"))

    first_dataset_link = page.locator(
        ".organization-datasets__list .usa-collection__heading a"
    ).first
    first_dataset_link.click()

    # ensure returning back to search results is present
    back_results = page.locator(".return-link")
    expect(back_results).to_contain_text("Return to search results")

    # navigate back to the org search results
    back_results.click()

    # finally, check i navigated back to what i initially queried
    expect(page).to_have_url(
        f"{base_url.rstrip('/')}/organization/test-org?q=2020&sort=relevance"
    )


def test_organization_detail_shows_code_repo_url_when_present(page):
    """Test that organization detail page shows repository link when URL is set."""
    page.goto("/organization/gsa")

    # Verify the Source Code Repository link is visible
    repo_link = page.locator('a[href="https://github.com/GSA"]')
    expect(repo_link).to_be_visible()

    # Verify the link text shows the URL
    expect(repo_link).to_have_text("https://github.com/GSA")

    # Verify the link has correct security attributes
    expect(repo_link).to_have_attribute("target", "_blank")
    expect(repo_link).to_have_attribute("rel", "noopener noreferrer")

    # Verify the label is present
    expect(page.locator("text=Source Code Repository:")).to_be_visible()


def test_organization_detail_hides_code_repo_url_when_not_set(page):
    """Test that organization detail page does NOT show repository field when URL is not set."""
    page.goto("/organization/no-repo-agency")

    # Verify the Source Code Repository label is NOT present
    expect(page.locator("text=Source Code Repository:")).not_to_be_visible()


def test_organization_detail_code_repo_link_opens_in_new_tab(page, context):
    """Test that clicking the repository link opens GitHub in a new tab."""
    page.goto("/organization/nasa")

    # Verify the NASA repo link is visible
    repo_link = page.locator('a[href="https://github.com/nasa"]')
    expect(repo_link).to_be_visible()

    # Listen for new page (tab) to open
    with context.expect_page() as new_page_info:
        repo_link.click()

    # Verify new tab opened with correct URL
    new_page = new_page_info.value
    expect(new_page).to_have_url(re.compile(r"github\.com/nasa"))
