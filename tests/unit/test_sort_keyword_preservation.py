import re
from pathlib import Path


def test_sort_change_does_not_drop_keyword_filters():
    """Changing the sort order must preserve active keyword filters.

    Sort now lives in the results header as its own control associated with the
    main search form (``form="main-search-form"``). Changing it submits that
    form, which carries the active keywords (server-rendered hidden inputs plus
    the autocomplete's submit-time sync), so the keyword filters survive a sort
    change.
    """
    repo_root = Path(__file__).resolve().parents[2]
    dropdowns_js = (repo_root / "app/static/js/filter_dropdowns.js").read_text(
        encoding="utf-8"
    )
    autocomplete_js = (repo_root / "app/static/js/filters_autocomplete.js").read_text(
        encoding="utf-8"
    )

    # The sort control submits its associated form on change.
    assert "initSortControl" in dropdowns_js
    assert "requestSubmit" in dropdowns_js
    assert re.search(r"getElementById\(\s*['\"]sort-select['\"]\s*\)", dropdowns_js)

    # The keyword autocomplete syncs selected keywords onto the main search form
    # when it is submitted, so a sort-triggered submit keeps the keywords.
    assert re.search(
        r"this\.mainSearchForm\.addEventListener\(\s*['\"]submit['\"]",
        autocomplete_js,
    )
    assert "syncHiddenInputsToMainSearch" in autocomplete_js
