# How To Add Search Filters

Search filters are registered in `app/search/filters/` and composed by the search registry in `app/search/registry.py`. A filter definition owns how a request parameter is parsed, how it is preserved in URLs, how it becomes an OpenSearch filter clause, how it appears in OpenAPI docs, and how it is rendered in the filter sidebar.

The hypothetical theme filter below (`app/search/filters/theme.py` does not exist yet) shows the pattern:

```python
THEME_FILTER = FilterDefinition(
    name="theme",
    query_params=("theme",),
    parse_contexts=(MAIN_CONTEXT, API_CONTEXT, ORGANIZATION_CONTEXT),
    ui_contexts=(MAIN_CONTEXT, ORGANIZATION_CONTEXT),
    label="Theme",
    renderer="checkbox_group",
    options=THEME_OPTIONS,
    api_query_params=(ApiQueryParam("theme", repeated=True),),
    parse=lambda args: get_list(args, "theme"),
    to_query_pairs=lambda values: [("theme", value) for value in values],
    clause_builder=_clause,
    section_builder=_section,
)
```

## 1. Create A Filter Module

Add a file under `app/search/filters/`, usually named for the logical filter, such as `theme.py`.

Define a `FilterDefinition` with these fields:

- `name`: Internal key stored on `SearchCriteria.filters`.
- `query_params`: Query string names owned by the filter. These are excluded from hidden form state when the filter is rendered visibly.
- `parse_contexts`: Routes that should parse the filter. Use `MAIN_CONTEXT`, `API_CONTEXT`, and/or `ORGANIZATION_CONTEXT`.
- `ui_contexts`: Pages where the filter should be visible in the sidebar.
- `api_query_params`: OpenAPI query parameter metadata for `/search`.
- `parse`: Request argument parser. Use helpers such as `get_list`, `parse_string`, and `parse_bool_param`.
- `to_query_pairs`: Converts the active filter value back into query string pairs for forms, pagination, and HTMX URLs.
- `clause_builder`: Converts the active filter value into one or more OpenSearch filter clauses.
- `section_builder`: Supplies renderer-specific sidebar data.

## 2. Choose A Renderer

The generic sidebar in `app/templates/components/filter_sidebar.html` supports these renderer values:

- `checkbox_group`: Repeated values such as organization type or theme.
- `radio_group`: Single-choice values such as spatial data.
- `keyword`: Keyword autocomplete and chips.
- `organization`: Organization autocomplete.
- `publisher`: Publisher autocomplete.
- `geography`: Geography search controls.

For a `checkbox_group`, the section should include:

```python
{
    "field_name": "theme",
    "values": values,
    "subtitle": "Dataset topic categories",
    "section_id": "filter-theme",
    "button_id": "theme-label",
    "active_summary": selection_summary(values),
}
```

The options can be static, as with theme, or supplied dynamically by overriding `options` in the section dictionary.

## 3. Register The Filter

Import the filter in `app/search/filters/__init__.py`, add it to `__all__`, and place it in the `FILTERS` tuple where it should appear in the sidebar and registry loops.

```python
from app.search.filters.theme import THEME_FILTER

FILTERS = (
    GEOGRAPHY_FILTER,
    KEYWORD_FILTER,
    ORGANIZATION_FILTER,
    ORGANIZATION_TYPE_FILTER,
    PUBLISHER_FILTER,
    THEME_FILTER,
    SPATIAL_DATA_FILTER,
    COLLECTION_FILTER,
)
```

Registration is what makes the filter available to request parsing, OpenSearch filter building, URL generation, OpenAPI docs, and visible sidebar sections.

## 4. Add Criteria Accessors When Useful

If route code or tests need a named accessor, add a property to `SearchCriteria`.

```python
@property
def themes(self) -> list[str]:
    return list(self.get_filter("theme", []))
```

Many filters do not need route-specific plumbing because `criteria.to_query_pairs()`, `criteria.to_query_dict()`, and `build_filter_sections()` already iterate over the registered filters.

## 5. Check OpenSearch Fields

Make sure the OpenSearch document has a field that can support the filter clause. The theme filter uses `match_phrase` against the indexed `theme` field:

```python
def _clause(criteria, values: list[str]) -> dict:
    return {
        "bool": {
            "should": [
                {"match_phrase": {"theme": {"query": value}}} for value in values
            ],
            "minimum_should_match": 1,
        }
    }
```

If a new filter needs exact case-insensitive matching or aggregations, update the mapping in `app/database/opensearch.py` so the field has a `keyword` subfield such as `raw` or `normalized`.

## 6. Verify Manually

After adding a filter, check the affected flows:

- Main search parses and persists the query parameter.
- Organization detail search parses and persists the query parameter, if included in `ORGANIZATION_CONTEXT`.
- `/search` accepts the query parameter and includes it in OpenAPI docs, if included in `API_CONTEXT`.
- Sorting, pagination, HTMX "show more", and clear filters preserve or remove the filter as expected.
- The OpenSearch query contains the expected filter clause.

Add or update tests when the change affects important behavior. For small UI-only additions, manual verification may be enough for the PR.
