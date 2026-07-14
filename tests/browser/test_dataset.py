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

    expect(button).to_have_text(re.compile(r"\+\s+(\d+)\s+more"))
    expected_count = 42

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


def test_dcat_3_0_normalized_fields(page):
    page.goto("/dataset/test-dcat-3-0")

    expect(page.get_by_role("heading", level=1)).to_have_text(
        "DCAT-US 3.0 Test Dataset"
    )

    description_section = page.locator(".dataset-description")
    expect(description_section).to_contain_text(
        "This is a sample dataset using DCAT-US 3.0 schema"
    )

    publisher_meta = page.locator(".dataset-meta")
    expect(publisher_meta).to_contain_text("Sample Federal Agency")
    expect(publisher_meta).not_to_contain_text("subOrganizationOf")
    expect(publisher_meta).not_to_contain_text("Department of Sample Services")

    contact_section = page.locator(".sidebar-section:has-text('Contact')")
    name_item = contact_section.locator(".sidebar-section__item:has-text('Name')")
    expect(name_item.get_by_text("Name", exact=False)).to_be_visible()
    expect(name_item.locator(".sidebar-section__value")).to_have_text("Jane Doe")

    email_item = contact_section.locator(".sidebar-section__item:has-text('Email')")
    expect(email_item.get_by_text("Email", exact=False)).to_be_visible()
    expect(email_item.locator("a[href='mailto:jane.doe@example.gov']")).to_be_visible()

    license_section = page.locator(".sidebar-section:has-text('Access & Use')")
    expect(license_section.get_by_text("License", exact=False)).to_be_visible()
    expect(
        license_section.locator(".sidebar-section__value:has-text('creativecommons')")
    ).to_be_visible()

    access_level_item = license_section.locator(
        ".sidebar-section__item:has-text('Access Level')"
    )
    expect(access_level_item.get_by_text("Access Level", exact=False)).to_be_visible()
    expect(access_level_item.locator(".sidebar-section__value")).to_have_text("public")

    dataset_info_section = page.locator(
        ".sidebar-section:has-text('Dataset Information')"
    )

    expect(
        dataset_info_section.get_by_text("Dataset First Published", exact=False)
    ).to_be_visible()
    expect(
        dataset_info_section.locator(
            ".sidebar-section__value:has-text('January 15, 2020')"
        )
    ).to_be_visible()

    expect(
        dataset_info_section.get_by_text("Dataset Last Updated", exact=False)
    ).to_be_visible()
    expect(
        dataset_info_section.locator(
            ".sidebar-section__value:has-text('October 01, 2024')"
        )
    ).to_be_visible()

    expect(
        dataset_info_section.get_by_text("Accrual Periodicity", exact=False)
    ).to_be_visible()
    expect(
        dataset_info_section.locator(".sidebar-section__value:has-text('annually')")
    ).to_be_visible()

    resources_section = page.locator(".resources-section")
    expect(resources_section.get_by_text("3 resources available")).to_be_visible()

    csv_resource = resources_section.locator(".resources-list__item").filter(
        has_text="Sample CSV Data File"
    )
    expect(csv_resource).to_be_visible()
    expect(csv_resource.locator(".resources-list__format")).to_have_text("CSV")
    expect(
        csv_resource.locator("a[href='https://example.gov/data/sample-data.csv']")
    ).to_be_visible()

    json_resource = resources_section.locator(".resources-list__item").filter(
        has_text="Sample JSON Data File"
    )
    expect(json_resource).to_be_visible()
    expect(json_resource.locator(".resources-list__format")).to_have_text("JSON")

    api_resource = resources_section.locator(".resources-list__item").filter(
        has_text="Sample API Endpoint"
    )
    expect(api_resource).to_be_visible()
    expect(api_resource.locator(".resources-list__format")).to_have_text("API")

    tags_section = page.locator(
        "text=Click any tag below to search for similar datasets"
    )
    expect(tags_section).to_be_visible()
    expect(page.locator("a[href='/?keyword=sample']")).to_be_visible()
    expect(page.locator("a[href='/?keyword=testing']")).to_be_visible()
    expect(page.locator("a[href='/?keyword=dcat-us-3.0']")).to_be_visible()
    expect(page.locator("a[href='/?keyword=climate']")).to_be_visible()
    expect(page.locator("a[href='/?keyword=environment']")).to_be_visible()
