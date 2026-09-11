"""Accessibility checks driven by axe-core.

These complement the pa11y-ci suite (see .pa11yci). pa11y uses HTML_CodeSniffer,
axe-core uses a different rule engine, so the two catch overlapping but distinct
issues. Neither replaces manual screen reader testing.
"""

import pytest
from axe_playwright_python.sync_playwright import Axe

# Advisory, not blocking -- see the marker definition in pyproject.toml.
pytestmark = pytest.mark.accessibility

# WCAG 2.0/2.1 level A and AA -- the standard data.gov is held to. axe also
# ships "best-practice" rules that are not WCAG requirements; those are checked
# separately in test_no_best_practice_regressions so a non-normative opinion
# can never fail the WCAG assertion.
WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]

# Rules that already fail on main. Listed explicitly so they show up as known
# debt rather than silently lowering the bar -- remove an entry once it's fixed.
KNOWN_VIOLATIONS = {
    # The two footer blocks sit outside any landmark. Fixing means restructuring
    # footer.html, which is more than an a11y-only change.
    "region",
    # The "Show more results" htmx div is a direct child of <ul class="usa-collection">
    # in dataset_results.html. Moving it out means reworking the hx-target/hx-swap
    # pair that replaces it, so it is tracked rather than fixed here.
    "list",
    # Dataset cards use <h3> for their titles, but the surrounding results section
    # has no <h2>, so the first card jumps h1 -> h3. Choosing the right level for
    # the results region is a content decision, not a markup typo.
    "heading-order",
    # The organization link in .dataset-meta carries no usa-link class, so it is
    # set apart from the surrounding text by colour alone. Underlining it is a
    # visual-design call for the design owners.
    "link-in-text-block",
}

COLLECTION_URL = (
    "/?collection=https%3A%2F%2Fsubdomain.domain%2Fparent%2Fexample.shp.iso.xml"
)

PAGES = [
    pytest.param("/", id="home"),
    pytest.param("/?q=health", id="search-results"),
    pytest.param(COLLECTION_URL, id="collection"),
    pytest.param("/organization", id="organization-list"),
    pytest.param("/organization/test-org", id="organization-detail"),
    pytest.param("/dataset/test", id="dataset-detail"),
]


def _format(violations):
    """Render violations as a readable pytest failure message."""
    lines = []
    for violation in violations:
        lines.append(
            f"[{violation['impact']}] {violation['id']}: {violation['help']} "
            f"({len(violation['nodes'])} node(s))"
        )
        lines.append(f"    {violation['helpUrl']}")
        for node in violation["nodes"][:5]:
            lines.append(f"    {' '.join(node['target'])}")
            lines.append(f"      {node['html'][:160]}")
    return "\n".join(lines)


def _run(page, url, options):
    page.goto(url)
    # axe needs a settled DOM: the filter sidebar and accordions are revealed by
    # JS on load, and auditing mid-render produces spurious results.
    page.wait_for_load_state("networkidle")
    return Axe().run(page, options=options).response["violations"]


@pytest.mark.parametrize("url", PAGES)
def test_no_wcag_violations(page, url):
    """Every page must be free of axe-detectable WCAG 2.1 AA violations."""
    violations = _run(page, url, {"runOnly": {"type": "tag", "values": WCAG_TAGS}})
    unexpected = [v for v in violations if v["id"] not in KNOWN_VIOLATIONS]
    assert not unexpected, f"axe found WCAG violations on {url}:\n{_format(unexpected)}"


@pytest.mark.parametrize("url", PAGES)
def test_no_best_practice_regressions(page, url):
    """Guard axe's best-practice rules (landmarks, heading order, region)."""
    violations = _run(page, url, {})
    unexpected = [v for v in violations if v["id"] not in KNOWN_VIOLATIONS]
    assert (
        not unexpected
    ), f"axe found best-practice violations on {url}:\n{_format(unexpected)}"


def test_axe_is_actually_running(page):
    """Guard against the suite silently passing because axe never ran.

    Without this, a broken axe injection (CSP change, bad upgrade) would make
    every assertion above vacuously true.
    """
    page.goto("/")
    page.wait_for_load_state("networkidle")
    page.evaluate("""() => {
            const img = document.createElement('img');
            img.src = '/assets/img/logo.svg';
            document.body.prepend(img);
        }""")
    violations = Axe().run(
        page, options={"runOnly": {"type": "rule", "values": ["image-alt"]}}
    )
    found = {v["id"] for v in violations.response["violations"]}
    assert "image-alt" in found, (
        "axe did not flag an image with no alt text -- the axe run is not working, "
        f"so the other accessibility tests cannot be trusted. Got: {found}"
    )
