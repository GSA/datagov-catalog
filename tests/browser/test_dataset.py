from playwright.sync_api import expect

"""Test the dataset details page."""


def test_dataset_details(page):
    page.goto("/dataset/test-climate-environment")
    expect(page.get_by_role("heading", level=1)).to_have_text(
        "Climate Change Environmental Data"
    )
