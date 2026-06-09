"""Shared helpers for Playwright filter interaction tests."""

import re

from playwright.sync_api import Locator, Page, expect

RESULTS_SUMMARY = "#search-results div.usa-prose p:first-child"
RESULT_HEADINGS = ".usa-collection__heading"


def keyword_input(page: Page) -> Locator:
    return page.get_by_placeholder("Type a keyword...")


def publisher_input(page: Page) -> Locator:
    return page.get_by_placeholder("Type a publisher name...")


def organization_input(page: Page) -> Locator:
    return page.get_by_placeholder("Type an organization name...")


def geography_input(page: Page) -> Locator:
    return page.get_by_placeholder("Type a place...")


def sort_select(page: Page) -> Locator:
    return page.get_by_label("Sort by")


def org_type_checkbox(page: Page, label: str) -> Locator:
    return page.get_by_role("checkbox", name=label)


def spatial_radio(page: Page, label: str) -> Locator:
    return page.get_by_role("radio", name=label, exact=True)


def check_org_type_checkbox(page: Page, label: str) -> None:
    section = page.locator('[data-filter-section="filter-organization"]')
    section.scroll_into_view_if_needed()
    section.get_by_text(label, exact=True).click()
    expect(org_type_checkbox(page, label)).to_be_checked()


def check_spatial_radio(page: Page, label: str) -> None:
    section = page.locator('[data-filter-section="filter-spatial"]')
    section.scroll_into_view_if_needed()
    section.get_by_text(label, exact=True).click()
    expect(spatial_radio(page, label)).to_be_checked()


def open_filter_sidebar(page: Page) -> None:
    """Ensure the filter sidebar panel is visible before interacting with controls."""
    panel = page.locator("#filter-sidebar-panel")
    panel.wait_for(state="attached")
    toggle = page.get_by_role("button", name=re.compile(r"Show filters", re.I))
    if not panel.is_visible():
        toggle.click()
    expect(panel).to_be_visible()


def expand_filter_section(page: Page, section_id: str) -> None:
    """Expand a collapsed filter accordion section."""
    section = page.locator(f'[data-filter-section="{section_id}"]')
    content = section.locator(".usa-accordion__content")
    button = section.get_by_role("button").first
    if not content.is_visible():
        button.click()
    expect(content).to_be_visible()
    section.scroll_into_view_if_needed()


def wait_for_filtered_results(page: Page) -> None:
    expect(page.locator(RESULTS_SUMMARY)).to_contain_text(
        re.compile(r"(matching filters|and filters)", re.I)
    )


def expect_result_visible(page: Page, title: str) -> None:
    expect(page.locator(RESULT_HEADINGS).filter(has_text=title)).to_be_visible()


def expect_result_hidden(page: Page, title: str) -> None:
    expect(page.locator(RESULT_HEADINGS).filter(has_text=title)).to_have_count(0)
