# Catalog API Changelog

This changelog documents consumer-facing changes to the Data.gov Catalog API.

Changes that may affect API consumers are documented here, including changes
to endpoints, request parameters, response fields, response formats,
pagination, ordering, authentication, and deprecations.

Issues that result in an entry in this changelog should be labeled
`changelog` in the GSA/data.gov issue tracker.

## Unreleased

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
