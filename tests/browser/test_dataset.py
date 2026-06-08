import re

from playwright.sync_api import expect

"""Test the dataset details page."""


def test_dataset_details(page):
    page.goto("/dataset/test-climate-environment")
    expect(page.get_by_role("heading", level=1)).to_have_text(
        "Climate Change Environmental Data"
    )


def test_dataset_tags_expand_button(page):
    page.goto("/dataset/parent-harvest-record")

    button = page.locator(".show-more-btn")
    extra_tags = page.locator(".extra-tags")
    hidden_tag_links = extra_tags.locator(".tag-link")

    initial_text = button.inner_text()
    expected_count = int(re.search(r"\d+", initial_text).group())

    assert expected_count == 42

    expect(button).to_be_visible()
    expect(button).to_have_text(f"+ {expected_count} more")

    # Hidden by default
    expect(extra_tags).to_have_class(re.compile(r"display-none"))
    expect(hidden_tag_links).to_have_count(expected_count)

    # Expand hidden tags
    button.click()

    expect(extra_tags).not_to_have_class(re.compile(r"display-none"))
    expect(button).to_have_text("Show less")

    # Collapse hidden tags
    button.click()

    expect(extra_tags).to_have_class(re.compile(r"display-none"))
    expect(button).to_have_text(f"+ {expected_count} more")
