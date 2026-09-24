from playwright.sync_api import expect


def test_contact_page_loads(page):
    """Test that contact page loads and displays form."""
    page.goto("/contact")

    expect(page.locator("h1")).to_contain_text("Contact Us")
    expect(page.locator("#name")).to_be_visible()
    expect(page.locator("#email")).to_be_visible()
    expect(page.locator("#message")).to_be_visible()
    expect(page.get_by_role("button", name="Send Message")).to_be_visible()


def test_contact_form_validation(page):
    """Test that form validates required fields."""
    page.goto("/contact")

    page.get_by_role("button", name="Send Message").click()

    expect(page.locator(".usa-alert--error")).to_be_visible()


def test_contact_navigation_link(page):
    """Test that Contact link in navigation works."""
    page.goto("/")

    page.get_by_role("link", name="Contact").click()

    expect(page).to_have_url("http://localhost:8080/contact")
