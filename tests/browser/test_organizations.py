
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
    expect(page.locator("li.usa-summary-box__item").nth(1)).to_have_text(re.compile("Total datasets: \d+"))


def test_organization_detail_keyword_click(page):
    page.goto("/organization/test-org")
    # click a keyword bubble
    page.get_by_role("button", name="americorps").click()

    expect(page.locator("div.usa-prose p:first-child")).to_have_text(
        re.compile(r"^\s*Found 41 datasets matching\s+filters\.")
    )

