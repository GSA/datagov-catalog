"""Blocking regression tests for badge colors and small-text contrast.

Deliberately not marked `accessibility`: these checks must run in the normal
browser CI, independently of the advisory page-wide axe exceptions.
"""

import re

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect

from tests.contrast import contrast_ratio

BADGES = "ul.dataset-resources .label"
COLLECTION_URL = (
    "/?collection=https%3A%2F%2Fsubdomain.domain%2Fparent%2Fexample.shp.iso.xml"
)


def _assert_badge(badge):
    match = re.search(r"\bbadge-color-([0-9a-f]{6})\b", badge.get_attribute("class"))
    assert match, "Badge must carry its format's color class"
    expected = tuple(bytes.fromhex(match[1]))
    styles = badge.evaluate("""el => {
            const css = getComputedStyle(el);
            return {foreground: css.color, background: css.backgroundColor,
                    filter: css.filter, outline: css.outlineStyle,
                    outlineWidth: parseFloat(css.outlineWidth),
                    decoration: css.textDecorationLine};
        }""")
    foreground = tuple(map(float, re.findall(r"[\d.]+", styles["foreground"])))
    background = tuple(map(float, re.findall(r"[\d.]+", styles["background"])))
    assert background == expected, (badge.inner_text(), styles)
    assert foreground == (255, 255, 255)
    assert styles["filter"] == "none"
    assert contrast_ratio(foreground, background) >= 4.5
    return styles


def _assert_all_badges(page):
    badges = page.locator(BADGES)
    assert badges.count() > 0, "Fixture must render badges for this page"
    for badge in badges.all():
        _assert_badge(badge)


def test_entire_badge_palette_renders_with_contrast_at_rest_and_hover(page):
    page.goto("/style-guide/icons")
    badges = page.locator(BADGES)
    assert badges.count() > 1
    for badge in badges.all():
        _assert_badge(badge)
        badge.hover()
        _assert_badge(badge)
        page.mouse.move(0, 0)
    # The last sample exercises the unknown-format fallback.
    expect(badges.last).to_have_css("background-color", "rgb(61, 69, 81)")


def test_format_colors_do_not_depend_on_stylesheet_order(page):
    page.goto("/style-guide/icons")
    page.evaluate("""() => {
        const badgeStyle = [...document.querySelectorAll('head style')]
            .find(el => el.textContent.includes('badge-color-'));
        if (!badgeStyle) throw new Error('Missing badge stylesheet');
        badgeStyle.parentNode.insertBefore(
            badgeStyle, document.querySelector('link[rel=stylesheet]'));
    }""")
    _assert_all_badges(page)


def test_badge_links_keep_colors_and_destinations_on_hover_and_keyboard_focus(page):
    page.goto("/?q=health")
    badges = page.locator("ul.dataset-resources a.label")
    assert badges.count() > 0
    # Exercise each available format once, without repeatedly testing duplicates.
    seen = set()
    for badge in badges.all():
        fmt = badge.get_attribute("data-format")
        if fmt in seen:
            continue
        seen.add(fmt)
        destination = badge.get_attribute("href")
        label = badge.inner_text()
        _assert_badge(badge)
        badge.hover()
        assert "underline" in _assert_badge(badge)["decoration"]
        page.mouse.move(0, 0)
        # Move keyboard focus onto the actual link, rather than simulating a
        # mouse click that can suppress :focus-visible.
        badge.focus()
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")
        expect(badge).to_be_focused()
        focused = _assert_badge(badge)
        assert "underline" in focused["decoration"]
        assert focused["outline"] != "none" and focused["outlineWidth"] > 0
        assert badge.get_attribute("href") == destination
        assert badge.inner_text() == label


@pytest.mark.parametrize(
    "url",
    ["/style-guide/icons", "/", "/?q=health", "/organization/test-org", COLLECTION_URL],
)
def test_rendered_badges_pass_axe_contrast_without_exemptions(page, url):
    page.goto(url)
    _assert_all_badges(page)
    results = (
        Axe()
        .run(
            page,
            context={"include": ["ul.dataset-resources"]},
            options={
                "runOnly": {"type": "rule", "values": ["color-contrast"]},
                "resultTypes": ["violations", "passes", "incomplete"],
            },
        )
        .response
    )
    assert not results["violations"], results["violations"]
    assert not results["incomplete"], results["incomplete"]
    assert any(
        rule["id"] == "color-contrast" and rule["nodes"] for rule in results["passes"]
    )


@pytest.mark.parametrize(
    "url", ["/?q=health&results=1", "/organization/test-org?q=health&results=1"]
)
def test_badges_keep_their_colors_after_loading_more_results(page, url):
    page.goto(url)
    cards = page.locator(".organization-datasets__item")
    expect(cards).to_have_count(1)
    _assert_all_badges(page)
    with page.expect_response(lambda response: "/search?" in response.url):
        page.get_by_role("button", name="Show more results").click()
    expect(cards).not_to_have_count(1)
    _assert_all_badges(page)
