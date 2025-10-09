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
-- create a materialized view from harvest_record of the latest set of records for dcatus sources
CREATE materialized VIEW dataset
AS SELECT sq.ckan_name                          AS slug,
          sq.source_raw :: jsonb                AS dcat,
          org.id                                AS organization_id,
          hs.id                                 AS harvest_source_id,
          sq.id                                 AS harvest_record_id,
          0                                     AS popularity,
          sq.date_finished                      AS last_harvested_date,
          setweight(to_tsvector('english', COALESCE(sq.source_raw::jsonb->>'title', '')), 'A') ||
            setweight(to_tsvector('english',  COALESCE(sq.source_raw::jsonb->>'description', '')), 'B') ||
            setweight(to_tsvector('english',  COALESCE(sq.source_raw::jsonb->>'publisher', '')), 'B') ||
            setweight(to_tsvector('english',  COALESCE(array_to_string(ARRAY(SELECT jsonb_array_elements_text(sq.source_raw::jsonb->'keyword')), ' '), '')), 'C') ||
            setweight(to_tsvector('english',  COALESCE(sq.source_raw::jsonb->>'theme', '')), 'D') ||
            setweight(to_tsvector('english',  COALESCE(sq.source_raw::jsonb->>'identifier', '')), 'D')
          AS search_vector,
          Md5(sq.identifier
              || sq.harvest_source_id)          AS id
   FROM  (SELECT DISTINCT ON (identifier, harvest_source_id) *
          FROM   harvest_record
          WHERE  status = 'success'
          ORDER  BY identifier,
                    harvest_source_id,
                    date_created DESC) sq
         LEFT JOIN harvest_source hs
                ON ( sq.harvest_source_id = hs.id )
         LEFT JOIN organization org
                ON ( hs.organization_id = org.id )
          WHERE  sq.action != 'delete'
                  AND hs.schema_type :: text LIKE 'dcatus1.1:%';

-- add indexes (materialized views don't inherit)
CREATE INDEX on dataset (slug);
CREATE INDEX on dataset (organization_id);
CREATE INDEX on dataset (harvest_source_id);
CREATE INDEX ON dataset (harvest_record_id);
CREATE INDEX ON dataset (last_harvested_date);
CREATE INDEX ON dataset USING GIN (search_vector);

-- example command to drop the view (if needed)
DROP MATERIALIZED VIEW dataset;
```
