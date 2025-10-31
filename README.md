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

## "dataset" materialized view

- the UI reads from a materialized view called "dataset" in a read-only database. an example command is provided below.

```sql
-- function for converting jsonb docs to search vector
CREATE OR REPLACE FUNCTION public.doc_to_search_vector(source_doc jsonb)
RETURNS tsvector
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
  RETURN
    setweight(to_tsvector('english', COALESCE(source_doc->>'title', '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(source_doc->>'description', '')), 'B') ||
    setweight(to_tsvector('english', COALESCE(source_doc->>'publisher', '')), 'B') ||
    setweight(to_tsvector('english', COALESCE(array_to_string(ARRAY(SELECT jsonb_array_elements_text(source_doc->'keyword')), ' '), '')), 'C') ||
    setweight(to_tsvector('english', COALESCE(source_doc->>'theme', '')), 'D') ||
    setweight(to_tsvector('english', COALESCE(source_doc->>'identifier', '')), 'D');
END;
$$;

-- create "dataset" materialized view
CREATE MATERIALIZED VIEW dataset AS
SELECT
    sq.ckan_name                                                              AS slug,
    COALESCE(sq.source_transform, sq.source_raw::jsonb)                       AS dcat,
    org.id                                                                    AS organization_id,
    hs.id                                                                     AS harvest_source_id,
    sq.id                                                                     AS harvest_record_id,
    COALESCE(dvc.view_count, 0)                                               AS popularity,
    sq.date_finished                                                          AS last_harvested_date,
    doc_to_search_vector(COALESCE(sq.source_transform, sq.source_raw::jsonb)) AS search_vector,
    Md5(sq.identifier || sq.harvest_source_id)                                AS id
FROM ( SELECT DISTINCT ON (identifier, harvest_source_id)
        *
    FROM
        harvest_record
    WHERE
        status = 'success'
    ORDER BY
        identifier,
        harvest_source_id,
        date_created DESC) sq
    LEFT JOIN harvest_source hs ON (sq.harvest_source_id = hs.id)
    LEFT JOIN organization org ON (hs.organization_id = org.id)
    LEFT JOIN dataset_view_count dvc ON (sq.ckan_name = dvc.dataset_slug)
WHERE
    sq.action != 'delete'
    AND NOT (hs.schema_type::text NOT LIKE 'dcatus1.1:%'
        AND sq.source_transform IS NULL);

-- add indexes (materialized views don't inherit)
CREATE UNIQUE INDEX ON dataset(slug);
CREATE INDEX ON dataset(organization_id);
CREATE INDEX ON dataset(harvest_source_id);
CREATE UNIQUE INDEX ON dataset(harvest_record_id);
CREATE INDEX ON dataset(popularity);
CREATE INDEX ON dataset(last_harvested_date);
CREATE INDEX ON dataset USING GIN(search_vector);

-- example drop commands
DROP MATERIALIZED VIEW dataset;
DROP FUNCTION public.doc_to_search_vector;
```
