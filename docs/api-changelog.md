# Catalog API Changelog

This changelog documents consumer-facing changes to the Data.gov Catalog API.

Changes that may affect API consumers are documented here, including changes
to endpoints, request parameters, response fields, response formats,
pagination, ordering, authentication, and deprecations.

Issues that result in an entry in this changelog should be labeled
`changelog` in the GSA/data.gov issue tracker.

## Unreleased

### Added

#### Versioned API routes under /api/v1/ namespace

**Issue:** GSA/data.gov#5610  
**Endpoints:** All API routes now available under `/api/v1/` prefix

All programmatic API routes are now versioned under the `/api/v1/` namespace
for better discoverability and future versioning. This includes:

- `GET /api/v1/search` - Dataset search
- `GET /api/v1/dataset/<slug_or_id>` - Dataset detail
- `GET /api/v1/organizations` - Organizations list
- `GET /api/v1/publishers` - Publishers list
- `GET /api/v1/keywords` - Keywords list
- `GET /api/v1/locations/search` - Locations search
- `GET /api/v1/location/<id>` - Location detail
- `GET /api/v1/harvest_record/<id>` - Harvest record detail
- `GET /api/v1/harvest_record/<id>/raw` - Harvest record raw data
- `GET /api/v1/harvest_record/<id>/transformed` - Harvest record transformed data
- `GET /api/v1/opensearch/health` - OpenSearch health status
- `GET /api/v1/stats` - Catalog statistics

**Compatibility:** Existing routes without the `/v1/` prefix remain functional
for backward compatibility. The unversioned `/harvest_record/*` routes now
redirect (301 permanent) to their `/api/v1/harvest_record/*` equivalents.

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
