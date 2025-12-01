# datagov-catalog

New Data.gov catalog UI

## Local Development

- Copy the sample environment file before starting the app: `cp .env.sample .env`.
- Update values in `.env` as needed for your local services; the file is ignored by Git.

## Harvest Database Configuration

- This application reuses the harvest database defined in the
  [datagov-harvester repository](https://github.com/GSA/datagov-harvester).
  The SQLAlchemy models have been duplicated locally in `app/models.py` for
  isolation.
- Interact with the shared DB through `CatalogDBInterface`
  (`app/database/interface.py`), which mirrors the logic in the harvester
  repo and keeps query semantics consistent between apps.


## table "dataset_view_count" seeding
- This table stores the view count records for each dataset slug, and joined on dataset view refresh to fill the popularity column.

- The data is primarily populated from external sources such as Google Analytics.

- For testing purposes, the table can be seeded using this SQL script.

```sql
CREATE OR REPLACE FUNCTION public.generate_popularity()
RETURNS integer
LANGUAGE plpgsql
VOLATILE
AS $$
BEGIN
  RETURN CASE
    WHEN random() < 0.80 THEN (random() * 51)::integer                    -- 80%: 0-50
    WHEN random() < 0.90 THEN (51 + random() * 50)::integer               -- 10%: 51-100
    WHEN random() < 0.95 THEN (101 + random() * 900)::integer             -- 5%: 101-1000
    ELSE (1001 + random() * 4000)::integer                                -- 5%: 1001-5000
  END;
END;
$$;

-- To seed the table with fake view count,
-- delete all rows first
TRUNCATE TABLE dataset_view_count;

-- seed the table
INSERT INTO dataset_view_count (id, dataset_slug, view_count)
SELECT
    gen_random_uuid()::VARCHAR(36)  AS id,
    slug                            AS dataset_slug,
    generate_popularity()           AS view_count
FROM dataset;

```
