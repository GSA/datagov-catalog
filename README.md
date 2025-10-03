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
          sq.id                                 AS harvest_record_id,
          NULL                                  AS popularity,
          sq.date_finished                      AS last_harvested_date,
          To_tsvector('english', sq.source_raw) AS search_vector,
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
   WHERE  sq.action != 'delete'
          AND hs.schema_type :: text LIKE 'dcatus1.1:%';

-- drop the view 
DROP MATERIALIZED VIEW dataset
```