from playwright.sync_api import expect

"""Test basic pages using the browser."""


def test_home_page(page):
    page.goto("/")
    expect(page.locator("#catalog-search-heading")).to_contain_text(
        "Search datasets"
    )
    expect(page.get_by_role("heading", level=1)).to_contain_text("Search datasets")
    expect(page.get_by_role("heading", level=2, name="Filters")).to_be_visible()
