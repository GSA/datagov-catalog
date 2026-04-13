
from playwright.sync_api import expect

"""Test basic pages using the browser."""

def test_home_page(page):
    page.goto("/")
    expect(page.locator("#main-search-form label.usa-label")).to_contain_text("Search datasets")
