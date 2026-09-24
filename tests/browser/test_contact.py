from playwright.sync_api import expect


def test_contact_page_loads(page):
    """Test that contact page loads and displays form."""
    page.goto("/contact")

    expect(page.locator("h1")).to_contain_text("Contact Us")
    expect(page.locator("#name")).to_be_visible()
    expect(page.locator("#email")).to_be_visible()
    expect(page.locator("#subject")).to_be_visible()
    expect(page.locator("#message")).to_be_visible()
    expect(page.get_by_role("button", name="Send")).to_be_visible()


def test_contact_form_validation(page):
    """Test that form validates required fields."""
    page.goto("/contact")

    page.get_by_role("button", name="Send").click()

    expect(page.locator("#name:invalid")).to_be_visible()


def test_contact_form_fields(page):
    """Test that all form fields are present and functional."""
    page.goto("/contact")

    page.locator("#name").fill("Test User")
    page.locator("#email").fill("test@example.com")
    page.locator("#subject").fill("Test Subject")
    page.locator("#message").fill("This is a test message with enough content")

    expect(page.locator("#name")).to_have_value("Test User")
    expect(page.locator("#email")).to_have_value("test@example.com")
    expect(page.locator("#subject")).to_have_value("Test Subject")
