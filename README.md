# datagov-catalog

## About

**catalog.data.gov** is the public-facing dataset discovery and search application for Data.gov, serving 515,000+ datasets from 120+ federal, state, municipal, university, and tribal publishing organizations.

This is a custom **Python/Flask** web application that replaced the legacy CKAN-based catalog in 2025. It serves as the **display layer** in the Data.gov platform: [datagov-harvester](https://github.com/GSA/datagov-harvester) collects and stores dataset metadata in the shared harvest database, while catalog.data.gov reads from that database and displays the metadata to the public through search results, dataset detail pages, and organization pages. It is a **read-only consumer** that uses OpenSearch for full-text search.

### Key Characteristics
- **Read-only**: Does NOT write to the harvest database—only reads. All dataset metadata is written by datagov-harvester.
- **Database isolation**: SQLAlchemy models are duplicated locally in `app/models.py`. Interact with the shared DB through `CatalogDBInterface` (`app/database/interface.py`).
- **DCAT support**: Supports DCAT-US 3.0 metadata normalization via `app/dcat_normalizer.py`
- **Search**: Full-text search powered by OpenSearch (`app/database/opensearch.py`)
- **Production**: [catalog.data.gov](https://catalog.data.gov)
- **Legacy catalog** (through fall 2026): [catalog-old.data.gov](https://catalog-old.data.gov)

## Architecture

- **Web app**: Python 3.12+, Flask (APIFlask), HTMX for dynamic UI, served via NGINX proxy on cloud.gov
- **Database**: Shared Postgres instance (`datagov-harvest-db` service, managed by datagov-harvester)
- **Search**: OpenSearch (`((app_name))-opensearch` service on cloud.gov)
- **Storage**: S3 for sitemaps and static assets
- **Monitoring**: New Relic
- **Logging**: Logstack (cloud.gov log drain)

### Key Dependencies
- Flask 3.1+, Flask-SQLAlchemy, Flask-HTMX, Flask-Talisman (security headers)
- SQLAlchemy 2.0+, Psycopg 3.3+ (Postgres driver)
- OpenSearch-py 3.2+ (search client)
- GeoAlchemy2 (geospatial queries)
- BeautifulSoup4 (HTML parsing)
- APIFlask (OpenAPI documentation)

## Local Development

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ and [Poetry](https://python-poetry.org/)
- Node.js and npm (for static assets and accessibility testing)

### Setup & Running

```bash
# 1. Copy environment file
cp .env.sample .env

# 2. Install static assets (USWDS, SCSS compilation)
make install-static

# 3. Start app (Docker Compose: app, postgres, opensearch)
make up

# 4. Load test data (fixtures + sync to OpenSearch)
make load-test-data
```

App runs at http://localhost:8080

### Key Make Targets

| Target | Description |
|--------|-------------|
| `make up` | Start Docker Compose services (app, postgres, opensearch) |
| `make down` | Stop services |
| `make clean` | Stop and remove volumes |
| `make install-static` | Install and build static assets (USWDS, SCSS) |
| `make watch-static` | Watch and rebuild SCSS/JS on change |
| `make load-test-data` | Load test fixtures into DB and sync to OpenSearch |
| `make test` | Run pytest unit tests |
| `make test-pa11y` | Run pa11y accessibility tests (requires running app) |
| `make test-browser` | Run Playwright browser tests |
| `make lint-check` | Run ruff, isort, black linting checks |
| `make lint-fix` | Auto-fix linting issues |
| `make poetry-update` | Update Poetry to latest version |

### Pre-commit hooks

Optionally, install the Git pre-commit hooks to run `black`, `ruff`, and `isort` automatically before each commit. These run the same tools as `make lint-check`, but scoped to the files you're staging rather than the whole tree — CI still runs `make lint-check` across the full codebase. Run once per clone:
```
pip install pre-commit
pre-commit install
```
The hook configuration lives in `.pre-commit-config.yaml`. After this, the formatters run on staged files at commit time; if a formatter changes a file the commit is aborted so you can stage the fixes and commit again.

### Poetry

CI uses the latest Poetry release. Keep your local Poetry up to date:
```
make poetry-update
```

## Environment Variables

See `.env.sample` for full list. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URI` | Postgres connection string (auto-constructed from `DATABASE_*` vars) | `postgresql://...` |
| `DATABASE_SERVER` | Postgres host | `localhost` |
| `DATABASE_NAME` | Database name | `mydb` |
| `DATABASE_USER` | Database user | `myuser` |
| `DATABASE_PASSWORD` | Database password | `mypassword` |
| `DATABASE_PORT` | Database port | `5432` |
| `FLASK_SECRET_KEY` | Flask session signing key | (required) |
| `PORT` | App port | `8080` |
| `OPENSEARCH_HOST` | OpenSearch host | `localhost` |
| `CATALOG_BASE_URL` | Base URL for OpenSearch document links | `http://0.0.0.0:8080` |
| `SITE_URL` | Public site URL | (set in production) |
| `NEW_RELIC_LICENSE_KEY` | New Relic license key | (optional) |
| `NEW_RELIC_APP_NAME` | New Relic application name | (optional) |
| `NEW_RELIC_MONITOR_MODE` | Enable New Relic monitoring | `false` |
| `NEW_RELIC_LOG` | New Relic log file path | `/var/log/new_relic.log` |
| `NEW_RELIC_LOG_LEVEL` | New Relic log level | `info` |
| `NEW_RELIC_HOST` | New Relic collector host | `gov-collector.newrelic.com` |
| `SITEMAP_AWS_REGION` | AWS region for sitemap S3 bucket | `us-east-1` |
| `SITEMAP_AWS_ACCESS_KEY_ID` | AWS access key for sitemap S3 bucket | (optional) |
| `SITEMAP_AWS_SECRET_ACCESS_KEY` | AWS secret key for sitemap S3 bucket | (optional) |
| `SITEMAP_S3_BUCKET` | S3 bucket for sitemaps | (optional) |

**Note:** In staging/prod, secrets are managed via cloud.gov user-provided services. See the [cloud.gov wiki page](https://github.com/GSA/data.gov/wiki/cloud.gov) for secrets management procedures.

## Deployment

**Automated via GitHub Actions** on push to `main`:
1. **Lint** — runs ruff Python linting
2. **Deploy to staging** — deploys to the `staging` cloud.gov space and runs a smoke test
3. **Deploy to prod** — deploys to the `prod` cloud.gov space and runs a smoke test (only runs after staging succeeds)

Cloud.gov spaces:
- `staging`
- `prod`

Deployment workflow: `.github/workflows/deploy.yml`

For emergency deployments, see: [Break Glass deployment](https://github.com/GSA/data.gov/wiki/Break-Glass-deployment)

## dataset_view_count seeding

The `dataset_view_count` table stores view count records for each dataset slug, used to populate the popularity column. Data is primarily populated from Google Analytics. For local testing, seed the table with:

```sql
CREATE OR REPLACE FUNCTION public.generate_popularity()
RETURNS integer
LANGUAGE plpgsql
VOLATILE AS $$
BEGIN
  RETURN CASE
    WHEN random() < 0.80 THEN (random() * 51)::integer
    WHEN random() < 0.90 THEN (51 + random() * 50)::integer
    WHEN random() < 0.95 THEN (101 + random() * 900)::integer
    ELSE (1001 + random() * 4000)::integer
  END;
END; $$;

TRUNCATE TABLE dataset_view_count;

INSERT INTO dataset_view_count (id, dataset_slug, view_count)
SELECT gen_random_uuid()::VARCHAR(36) AS id,
       slug AS dataset_slug,
       generate_popularity() AS view_count
FROM dataset;
```

## Local Accessibility Testing

We use pa11y-ci for accessibility testing.

1. Install dependencies: `npm install`
2. Load test data: `make load-test-data`
3. Run pa11y tests: `make test-pa11y`

## Related resources

- [harvest.data.gov](https://harvest.data.gov) -- harvest pipeline UI
- [datagov-harvester](https://github.com/GSA/datagov-harvester) -- harvester source code and shared DB
- [Data.gov wiki](https://github.com/GSA/data.gov/wiki) -- operational documentation
- [catalog.data.gov wiki page](https://github.com/GSA/data.gov/wiki/catalog.data.gov)
