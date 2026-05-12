"""Test organization list and organization detail pages."""

import re

from playwright.sync_api import expect


def test_organization_list(page):
    page.goto("/organization")
    expect(page.get_by_role("heading", level=2)).to_have_text("test org")


def test_organization_detail(page):
    page.goto("/organization/test-org")
    # title
    expect(page.get_by_role("heading", level=1)).to_have_text("test org")
    # dataset total
    expect(page.locator("li.usa-summary-box__item").nth(1)).to_have_text(
        re.compile("Total datasets: \d+")
    )


def test_organization_detail_keyword_click(page):
    page.goto("/organization/test-org")
    # click a keyword bubble
    page.get_by_role("button", name="americorps (41)", exact=True).click()

    expect(
        page.get_by_role("paragraph").filter(has_text="datasets matching")
    ).to_have_text(re.compile(r"^\s*Found 41 datasets matching\s+filters\."))


def test_organization_detail_return_to_search_results(page):
    page.goto("/organization/test-org")

    # submit query
    page.locator("#search-query").fill("2020")
    page.locator(".usa-button").nth(1).click()

    # navigate to the first dataset
    page.goto(page.locator(".usa-link").nth(0).get_attribute("href"))

    # ensure returning back to search results is present
    back_results = page.locator(".return-link")
    expect(back_results).to_contain_text("Return to search results")

    # navigate back to the org search results
    page.goto(back_results.get_attribute("href"))

    # finally, check i navigated back to what i initially queried
    expect(page).to_have_url(
        "http://localhost:8080/organization/test-org?q=2020&sort=relevance"
    )
