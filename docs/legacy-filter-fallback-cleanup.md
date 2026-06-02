# Legacy filter fallback cleanup

Temporary backward-compatibility code supports users who still have **cached old search HTML** (right-hand sidebar layout) while the CDN serves **new JavaScript**. Old pages only load three scripts:

- `filter_form_auto_submit.js`
- `filters_autocomplete.js`
- `geography_autocomplete.js`

New pages load the full filter-bar script set, including `geography_utils.js` and `geography_map_mixin.js`.

Remove the fallback code once everyone is on fresh HTML. Until then, old layout + new JS would crash or leave org/publisher/geography filters broken without these shims.

## When it is safe to remove

Do **not** remove on deploy day. Wait until cached HTML has rolled off.

1. Confirm develop/staging/prod HTML is the new layout for you and teammates (hard refresh or incognito).
2. In **View Page Source** (not DevTools Elements), verify search pages include:
   - `render_filter_bar` / `.filter-bar` markup (not `filter_sidebar` / `<aside class="desktop:grid-col-3">`)
   - `<script ... geography_utils.js">` and `<script ... geography_map_mixin.js">` before `geography_autocomplete.js`
3. Optionally ask cloud.gov support to confirm CDN TTL has passed or that a cache invalidation completed.
4. Watch client-side errors (New Relic, browser console on smoke checks) for `dataGovGeographyUtils` / `OrganizationAutocomplete` issues — none for a few days is a good signal.

If all of the above look good in **every environment you care about**, schedule cleanup.

## What to delete

### `app/static/js/geography_autocomplete.js`

Remove:

| Block | Purpose |
|-------|---------|
| `ensureDataGovGeographyUtils` IIFE (top of file) | Stub when `geography_utils.js` missing from old HTML |
| `requestFilterFormSubmit` function | Submit helper for pages without `filter_submit.js` |
| `isLegacyGeographyFacet` function | Detects old sidebar vs new filter bar |
| `geographySidebarFallback` object | Inline map + no-op panel methods for old HTML |
| Conditional mixin assign (`geographyMixin` / `geographySidebarFallback`) | Replace with direct `Object.assign(..., window.dataGovGeographyMapMixin)` |
| All `isLegacyGeographyFacet()` branches | Legacy immediate submit in `selectGeography`, `clearClicked`, `handleKeyDown` (Enter) |
| Guards on `initMapPanel` / `persistCurrentMapPanelStateForNextLoad` | Only needed when mixin may be absent |
| Legacy `displayGeometry` call at end of `init()` | Only for old sidebar on load |

After cleanup, `geography_autocomplete.js` should assume `geography_utils.js` and `geography_map_mixin.js` are always loaded before it (as in current templates).

### `app/static/js/geography_map_mixin.js`

Revert the defensive `OSM_ATTRIBUTION` line to use `window.dataGovGeographyUtils.OSM_ATTRIBUTION` directly (utils always loaded first in templates).

### `app/static/js/filters_autocomplete.js`

Remove:

| Block | Purpose |
|-------|---------|
| Top-level `requestFilterFormSubmit` function | Only required for old three-script HTML |
| Entire `OrganizationAutocomplete` class (~400 lines) | Legacy sidebar org filter |
| Entire `PublisherAutocomplete` class (~330 lines) | Legacy sidebar publisher filter |
| `DOMContentLoaded` init blocks for `#organization-input` and `#publisher-input` | Legacy sidebar only |

Restore keyword submit calls to use `window.dataGovFilterSubmit.request(...)` directly (new HTML always loads `filter_submit.js`).

**Expected file size:** drops from ~1,180 lines to ~400 lines.

## What to keep (not fallback)

These are part of the new filter bar, not legacy shims:

- `KeywordAutocomplete` in `filters_autocomplete.js`
- `filter_submit.js`, `filter_dropdowns.js`, `filter_controllers.js`, etc.
- `geography_utils.js` and `geography_map_mixin.js` as separate files

## Suggested cleanup PR checklist

- [ ] Verified new HTML in dev/stage/prod (page source, not cached tab)
- [ ] No CDN/cache overlap concerns (or invalidation done)
- [ ] Removed geography fallback blocks listed above
- [ ] Removed org/publisher legacy classes and init from `filters_autocomplete.js`
- [ ] Keyword autocomplete uses `dataGovFilterSubmit` again
- [ ] `tests/browser/test_search_sort_and_filters.py` passes
- [ ] Manual smoke: geography deferred Apply, org/publisher combo boxes, keyword chips on search + org detail pages
- [ ] Delete this doc in the same PR (or replace with a one-line note in the PR description that cleanup is complete)

## Related context

- Filter refactor merged to `develop` (sidebar → filter bar under search)
- cloud.gov external-domain CDN can cache HTML up to ~24h without origin `Cache-Control` headers
- See team wiki / cloud.gov docs on external domain service if cache invalidation is needed before cleanup
