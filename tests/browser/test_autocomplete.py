"""Playwright tests for the shared filter autocomplete base classes.

These tests require the demo filter fixture data loaded into the running app
(for example via ``make test-browser-with-data``).
"""

import re

import pytest
from playwright.sync_api import Page, expect

from tests.browser.filter_helpers import (
    expand_filter_section,
    geography_input,
    keyword_input,
    open_filter_sidebar,
    organization_input,
    publisher_input,
    wait_for_filtered_results,
)

FOCUSED_SUGGESTION = re.compile(r"keyword-suggestion--focused")
VISIBLE_SUGGESTIONS = re.compile(r"keyword-suggestions--visible")


@pytest.mark.parametrize(
    "child_class",
    [
        "KeywordAutocomplete",
        "OrganizationAutocomplete",
        "PublisherAutocomplete",
        "GeographyAutocomplete",
    ],
)
def test_filter_autocompletes_extend_base_autocomplete(
    page: Page, child_class: str
) -> None:
    page.goto("/")
    assert page.evaluate(f"{child_class}.prototype instanceof BaseAutocomplete")


@pytest.mark.parametrize(
    "child_class", ["OrganizationAutocomplete", "PublisherAutocomplete"]
)
def test_single_select_autocompletes_extend_single_select_base(
    page: Page, child_class: str
) -> None:
    page.goto("/")
    assert page.evaluate(f"{child_class}.prototype instanceof SingleSelectAutocomplete")


def test_keyword_suggestions_toggle_aria_expanded(page: Page) -> None:
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-keywords")
    keyword_input(page).fill("wildfire")

    expect(page.locator("#keyword-suggestions")).to_have_class(VISIBLE_SUGGESTIONS)
    expect(keyword_input(page)).to_have_attribute("aria-expanded", "true")

    keyword_input(page).press("Escape")

    expect(page.locator("#keyword-suggestions")).not_to_have_class(VISIBLE_SUGGESTIONS)
    expect(keyword_input(page)).to_have_attribute("aria-expanded", "false")


def test_geography_suggestions_toggle_aria_expanded(page: Page) -> None:
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-geography")
    geography_input(page).fill("Portland")

    expect(
        page.locator("#geography-suggestions .keyword-suggestion").first
    ).to_be_visible()
    expect(geography_input(page)).to_have_attribute("aria-expanded", "true")


def test_keyword_keyboard_selection_adds_chip(page: Page) -> None:
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-keywords")
    keyword_input(page).fill("wildfire")
    first_suggestion = page.locator("#keyword-suggestions .keyword-suggestion").first
    expect(first_suggestion).to_be_visible()

    keyword_input(page).press("ArrowDown")
    expect(first_suggestion).to_have_class(FOCUSED_SUGGESTION)
    keyword_input(page).press("Enter")

    wait_for_filtered_results(page)
    expect(
        page.locator('#keyword-chips .tag-link[data-keyword="wildfire"]')
    ).to_be_visible()


def test_publisher_suggestion_highlights_query(page: Page) -> None:
    with page.expect_response("**/api/publishers"):
        page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-publishers")
    publisher_input(page).fill("Portland")

    highlighted = page.locator(
        "#publisher-suggestions .keyword-suggestion__text strong"
    ).first
    expect(highlighted).to_have_text("Portland")


def test_organization_chip_removal_restores_input(page: Page) -> None:
    page.goto("/?org_slug=city-of-portland")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-organization-autocomplete")
    expect(organization_input(page)).to_be_hidden()

    page.locator("#organization-chips .keyword-chip__remove").click()

    expect(organization_input(page)).to_be_visible()
    expect(page.locator("#organization-chips .tag-link")).to_have_count(0)


def test_focusing_empty_keyword_input_keeps_suggestions_collapsed(page: Page) -> None:
    page.goto("/")
    open_filter_sidebar(page)
    expand_filter_section(page, "filter-keywords")
    keyword_input(page).focus()

    expect(page.locator("#keyword-suggestions")).not_to_have_class(VISIBLE_SUGGESTIONS)
    expect(keyword_input(page)).to_have_attribute("aria-expanded", "false")
