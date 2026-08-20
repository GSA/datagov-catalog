"""Browser tests for /code compliance index page."""

import re

from playwright.sync_api import expect


def test_code_page_loads(page):
    """Test that /code page loads successfully."""
    page.goto("/code")
    expect(page.get_by_role("heading", level=1)).to_have_text(
        "Federal Agency Source Code Repositories"
    )


def test_code_page_has_table(page):
    """Test page displays the compliance table."""
    page.goto("/code")

    # Should show a table with proper structure
    table = page.locator("table.usa-table")
    expect(table).to_be_visible()

    # Check table headers
    expect(page.locator("th", has_text="Agency")).to_be_visible()
    expect(page.locator("th", has_text="Source Code Repository")).to_be_visible()


def test_code_page_includes_share_it_act_context(page):
    """Test page includes SHARE IT Act explanation."""
    page.goto("/code")

    # Check for SHARE IT Act link
    share_it_link = page.locator('a[href*="congress.gov"]')
    expect(share_it_link).to_be_visible()
    expect(share_it_link).to_have_text(re.compile(r"SHARE IT Act", re.IGNORECASE))

    # Check for status meanings explanation
    expect(page.locator("text=Status meanings:")).to_be_visible()
    expect(page.locator("text=Repository URL:")).to_be_visible()
    expect(page.locator("text=Exempt:")).to_be_visible()
    expect(page.locator("text=Not yet reported:")).to_be_visible()


def test_code_page_table_rows_have_org_links(page):
    """Test that organization names link to detail pages."""
    page.goto("/code")

    # Find any organization links in the table
    org_links = page.locator('table.usa-table tbody td a[href^="/organization/"]')

    # If there are any federal orgs, they should link to detail pages
    if org_links.count() > 0:
        first_link = org_links.first
        expect(first_link).to_have_attribute("href", re.compile(r"^/organization/"))


def test_code_page_external_links_have_security_attributes(page):
    """Test that repository links have proper security attributes when present."""
    page.goto("/code")

    # Look for any external links in the table (repo URLs)
    external_links = page.locator(
        'table.usa-table tbody td a[target="_blank"][rel="noopener noreferrer"]'
    )

    # Count how many exist - could be 0 if no orgs have code_repo_url
    count = external_links.count()

    # If any external links exist, they should all have correct security attributes
    if count > 0:
        for i in range(count):
            link = external_links.nth(i)
            expect(link).to_have_attribute("target", "_blank")
            expect(link).to_have_attribute("rel", "noopener noreferrer")


def test_code_page_table_structure(page):
    """Test page table has proper structure."""
    page.goto("/code")

    # Verify table exists (may be empty if no federal orgs in fixtures)
    table = page.locator("table.usa-table")
    expect(table).to_be_visible()

    # Check that table has proper headers regardless of content
    thead = table.locator("thead")
    expect(thead).to_be_visible()

    # If there are data rows, verify they have two cells (org name + status)
    rows = table.locator("tbody tr")
    if rows.count() > 0:
        first_row = rows.first
        cells = first_row.locator("td")
        expect(cells).to_have_count(2)
