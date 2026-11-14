import pytest
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
    """Test that form fields are present and functional."""
    page.goto("/contact")

    page.locator("#name").fill("Test User")
    page.locator("#email").fill("test@example.com")
    page.locator("#subject").fill("Test Subject")
    page.locator("#message").fill("This is a test message with enough content")

    expect(page.locator("#name")).to_have_value("Test User")
    expect(page.locator("#email")).to_have_value("test@example.com")
    expect(page.locator("#subject")).to_have_value("Test Subject")


@pytest.mark.parametrize("form_type", [None, "default", "feedback", "usagov"])
def test_contact_honeypot_accessibility_and_submission(page, form_type):
    """The trap is submitted, but stays off screen and out of keyboard navigation."""
    page.goto("/contact")
    if form_type is None:
        form = page.locator("main form")
        name = form.locator('input[name="name"]')
        name.focus()
    else:
        page.locator("#contact-widget-button").click()
        page.locator(f'.contact-widget__menu-item[data-form="{form_type}"]').click()
        form = page.locator(f"#widget-form-{form_type} form")
        name = form.locator('input[name="name"]')
        expect(name).to_be_focused()

    field = form.locator('input[name="website"]')
    expect(field).to_have_attribute("type", "text")
    expect(field).not_to_be_in_viewport()
    expect(field).to_have_attribute("tabindex", "-1")
    expect(field).to_have_attribute("autocomplete", "off")
    expect(field.locator("..")).to_have_attribute("aria-hidden", "true")
    assert form.evaluate("form => new FormData(form).get('website')") == ""

    page.keyboard.press("Tab")
    expect(form.locator('input[name="email"]')).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(name).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(field).not_to_be_focused()

    name.fill("Test User")
    form.locator('input[name="email"]').fill("test@example.com")
    form.locator('input[name="subject"]').fill("Test Subject")
    form.locator('textarea[name="message"]').fill("Test message with enough content")
    # Intercept the POST so browser tests never send an actual email.
    page.route(
        "**/contact-submit",
        lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body='<div class="usa-alert usa-alert--success"><p class="usa-alert__text">Thank you</p></div>',
        ),
    )
    with page.expect_request("**/contact-submit") as request_info:
        form.get_by_role("button", name="Send").click()
    request = request_info.value
    assert request.method == "POST"
    if form_type is None:
        assert "website=" in request.post_data
    else:
        assert 'name="website"\r\n\r\n\r\n' in request.post_data
