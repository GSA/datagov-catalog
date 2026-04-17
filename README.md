# datagov-catalog

catalog.data.gov is the public-facing dataset discovery and search application for Data.gov. It serves 515,000+ datasets from 120+ federal, state, municipal, university, and tribal publishing organizations.

This application is a custom Python/Flask web application that replaced the legacy CKAN-based catalog in 2025. It reads from the shared harvest database managed by [datagov-harvester](https://github.com/GSA/datagov-harvester) and uses OpenSearch for full-text search.

- Production: [catalog.data.gov](https://catalog.data.gov)
- Legacy catalog (through fall 2026): [catalog-old.data.gov](https://catalog-old.data.gov)

## Architecture

- **Web app**: Python/Flask, served via NGINX proxy on cloud.gov
- **Database**: Shared Postgres instance managed by datagov-harvester (`datagov-harvest-db` service)
- **Search**: OpenSearch (`((app_name))-opensearch` service on cloud.gov)
- **Storage**: S3 for sitemaps and static assets
- **Monitoring**: New Relic
- **Logging**: Logstack (cloud.gov log drain)

The application does not write to the harvest database -- it reads only. All dataset metadata is written by datagov-harvester. The SQLAlchemy models are duplicated locally in `app/models.py` for isolation; interact with the shared DB through `CatalogDBInterface` (`app/database/interface.py`).

## Local Development

### Prerequisites

- Docker and Docker Compose
- Python 3.x and [Poetry](https://python-poetry.org/)
- Node.js and npm (for static assets and accessibility testing)

### Setup

1. Copy the sample environment file:
```
   cp .env.sample .env
```
2. Update values in `.env` as needed for your local services (file is ignored by Git)
3. Install static assets:
```
   make install-static
```
4. Start the app:
```
   make up
```
5. Load test data:
```
   make load-test-data
```

### Running tests

Run the full Python test suite:
```
make test
```

Run accessibility tests (requires running app):
```
make test-pa11y
```

Run linting:
```
make lint-check
```

Auto-fix linting:
```
make lint-fix
```

### Poetry

CI uses the latest Poetry release. Keep your local Poetry up to date:
```
make poetry-update
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `DATABASE_SERVER` | Postgres host (default: localhost) |
| `DATABASE_PORT` | Postgres port (default: 5432) |
| `DATABASE_NAME` | Postgres database name |
| `DATABASE_USER` | Postgres user |
| `DATABASE_PASSWORD` | Postgres password |
| `DATABASE_URI` | Full Postgres connection URI (auto-constructed from above) |
| `PORT` | App port (default: 8080) |
| `OPENSEARCH_HOST` | OpenSearch host (default: localhost) |
| `NEW_RELIC_LICENSE_KEY` | New Relic license key |
| `NEW_RELIC_APP_NAME` | New Relic app name |
| `NEW_RELIC_MONITOR_MODE` | Enable New Relic monitoring (true/false) |
| `NEW_RELIC_LOG` | New Relic log file path |
| `NEW_RELIC_LOG_LEVEL` | New Relic log level |
| `SITEMAP_AWS_REGION` | AWS region for sitemap S3 bucket |
| `SITEMAP_AWS_ACCESS_KEY_ID` | AWS access key for sitemap S3 bucket |
| `SITEMAP_AWS_SECRET_ACCESS_KEY` | AWS secret key for sitemap S3 bucket |
| `SITEMAP_S3_BUCKET` | S3 bucket name for sitemaps |

For cloud.gov deployments, secrets are managed via user-provided services. See the [cloud.gov wiki page](https://github.com/GSA/data.gov/wiki/cloud.gov) for secrets management procedures.

## Deployment

Deployments are triggered automatically via GitHub Actions on push to `main`. The [deploy workflow](https://github.com/GSA/datagov-catalog/blob/main/.github/workflows/deploy.yml) runs in this order:

1. **Lint** -- runs ruff Python linting
2. **Deploy to staging** -- deploys to the `staging` cloud.gov space and runs a smoke test
3. **Deploy to prod** -- deploys to the `prod` cloud.gov space and runs a smoke test (only runs after staging succeeds)

Cloud.gov spaces:
- `staging`
- `prod`

For emergency deployments outside of the normal CI/CD pipeline, see [Break Glass deployment](https://github.com/GSA/data.gov/wiki/Break-Glass-deployment).

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
