import re
from pathlib import Path


def test_sort_change_does_not_drop_keyword_filters():
    repo_root = Path(__file__).resolve().parents[1]
    auto_submit_js = (repo_root / "app/static/js/filter_form_auto_submit.js").read_text(
        encoding="utf-8"
    )
    autocomplete_js = (repo_root / "app/static/js/filters_autocomplete.js").read_text(
        encoding="utf-8"
    )

    assert "requestSubmit" in auto_submit_js
    assert re.search(
        r"attachInputAutoSubmit\(\s*form\s*,\s*\[[^\]]*select\[name=['\"]sort['\"]\][^\]]*\]\s*\)",
        auto_submit_js,
    )

    assert re.search(
        r"this\.form\.addEventListener\(\s*['\"]submit['\"]\s*,\s*\(\)\s*=>\s*this\.syncHiddenInputs\(\)\s*\)",
        autocomplete_js,
    )
