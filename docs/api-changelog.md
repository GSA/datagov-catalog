# Catalog API Changelog

This changelog documents consumer-facing changes to the Data.gov Catalog API.

Changes that may affect API consumers are documented here, including changes
to endpoints, request parameters, response fields, response formats,
pagination, ordering, authentication, and deprecations.

Issues that result in an entry in this changelog should be labeled
`changelog` in the GSA/data.gov issue tracker.

## Unreleased

### Added

#### Alphabetical dataset search ordering

**Issue:** GSA/data.gov#6512
**Endpoint:** `GET /search`

Use `sort=title` to order results by the full dataset title, ascending and
case-insensitive. For example: `/search?q=climate&keyword=temperature&sort=title`.
The original title is preserved in results. Accents, punctuation, and numbers
follow OpenSearch lexical ordering; this is not locale-specific or natural
numeric ordering. Missing titles appear last, and equal normalized titles are
ordered by document ID descending for stable pagination on an unchanged index.

The response reports `sort: "title"`. Continue pagination using the returned
`after` cursor with the same query, filters, and sort. Start without `after`
when changing the sort.

**Compatibility:** Additive; existing sort options and the default remain unchanged.

### Changed

#### Organizations list excludes organizations with no datasets

**Issue:** GSA/data.gov#5781  
**Endpoint:** `GET /api/organizations`

This endpoint now excludes organizations that have zero datasets, matching
the behavior of `/organization`. Previously it returned every organization
regardless of dataset count.

**Compatibility:** This is a potentially breaking change for API consumers
that relied on the previous response including organizations with no
datasets.
