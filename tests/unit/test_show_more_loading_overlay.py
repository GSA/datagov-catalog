import re
from pathlib import Path


def test_show_more_button_triggers_results_loading_overlay():
    repo_root = Path(__file__).resolve().parents[2]
    auto_submit_js = (repo_root / "app/static/js/filter_form_auto_submit.js").read_text(
        encoding="utf-8"
    )
    dataset_results_html = (
        repo_root / "app/templates/components/dataset_results.html"
    ).read_text(encoding="utf-8")
    dataset_results_org_html = (
        repo_root / "app/templates/components/dataset_results_organization.html"
    ).read_text(encoding="utf-8")

    assert "function hideResultsLoadingOverlay()" in auto_submit_js
    assert "showLoadingOverlay = showResultsLoadingOverlay" in auto_submit_js
    assert "hideLoadingOverlay = hideResultsLoadingOverlay" in auto_submit_js
    assert re.search(
        r"htmx:beforeRequest.*data-results-loading-overlay",
        auto_submit_js,
        re.DOTALL,
    )
    assert "htmx:afterSwap" in auto_submit_js
    assert "htmx:responseError" in auto_submit_js
    assert "htmx:sendError" in auto_submit_js

    for template in (dataset_results_html, dataset_results_org_html):
        assert re.search(
            r"<button[^>]*data-results-loading-overlay[^>]*>[\s\S]*Show more results",
            template,
        )
