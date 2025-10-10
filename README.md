# datagov-catalog

New Data.gov catalog UI

## Harvest Database Configuration

- This application reuses the harvest database defined in the
  [datagov-harvester repository](https://github.com/GSA/datagov-harvester).
  The SQLAlchemy models have been duplicated locally in `app/models.py` for
  isolation.
- Interact with the shared DB through `CatalogDBInterface`
  (`app/database/interface.py`), which mirrors the logic in the harvester
  repo and keeps query semantics consistent between apps.

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
    0                                                                         AS popularity,
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
