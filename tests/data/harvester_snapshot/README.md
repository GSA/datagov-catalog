# harvester_snapshot

A real Postgres + OpenSearch snapshot from a freshly migrated, freshly fixture-loaded
[datagov-harvester](https://github.com/GSA/datagov-harvester) instance, used as the baseline dataset
corpus for catalog's own test suite (layered under the hand-authored edge cases in `tests/fixtures.py` --
see `tests/unit/conftest.py`). GSA/data.gov#6211.

Generated from harvester `main` @ `65a846f8fb56fde28f562317209f017ad4603c85` (2026-08-04), after
GSA/data.gov#6209 merged.

## Why a snapshot instead of harvester's fixtures directly

Catalog's own CI needs *some* realistic corpus that isn't tied to `datagov-data-access` (which is
expected to be deprecated once #6209's re-vendoring settles) or to a live harvester checkout. A snapshot
is a static artifact: no cross-repo dependency, no ORM, loadable with plain `psql`/`opensearchpy` bulk
calls.

The corpus itself is thin -- harvester's fixtures produce 1 organization, 1 harvest source, 2 datasets,
0 locations -- which is why `tests/fixtures.py`'s hand-authored edge cases (DCAT-US 3.0, `isPartOf`
collections, spatial bboxes, stopword-matching titles, `locations` rows) still exist and are loaded
*in addition to* this snapshot, not instead of it.

## Files

- `postgres.sql` -- `pg_dump --data-only` of `organization`, `harvest_source`, `harvest_job`,
  `harvest_record`, `dataset`, `locations`. Column lists match catalog's own slim models in
  `app/models.py` exactly (verified when this was generated -- if a future regeneration adds/removes a
  harvester column, the load step in `tests/unit/conftest.py` will fail loudly with an "undefined column"
  error, not silently drop data).
- `opensearch.ndjson` -- bulk-format dump of the `datasets` index documents produced by indexing the same
  Postgres rows via harvester's `flask search compare --update`, i.e. real `DatasetDocument` output, not
  something catalog's own vendored writer produced.

## Regenerating

Requires a local `datagov-harvester` checkout, its docker environment, and `psql`. This cannot run in CI
-- only a human with both repos can produce it. Run from the **harvester** repo root:

```bash
make up
make load-test-data
docker exec datagov-harvester-app-1 flask search reset-mapping
docker exec datagov-harvester-app-1 flask search compare --update

docker exec datagov-harvester-db-1 pg_dump -U myuser -d mydb \
  --data-only --no-owner --no-acl --no-comments --disable-triggers \
  -t public.organization -t public.harvest_source -t public.harvest_job \
  -t public.harvest_record -t public.dataset -t public.locations \
  > /path/to/datagov-catalog/tests/data/harvester_snapshot/postgres.sql

curl -sk -u admin:admin "https://localhost:9200/datasets/_search?size=10000" | python3 -c "
import json, sys
hits = json.load(sys.stdin)['hits']['hits']
for hit in hits:
    print(json.dumps({'index': {'_index': 'datasets', '_id': hit['_id']}}))
    print(json.dumps(hit['_source']))
" > /path/to/datagov-catalog/tests/data/harvester_snapshot/opensearch.ndjson
```

`flask search reset-mapping` may report `Created index mapping does not match application mapping.` --
this is a known bug in the `dynamic` field's bool-vs-string comparison (see
GSA/datagov-harvester#809's fix), unrelated to this snapshot. The index is still created correctly; the
verification step is just wrong. Ignore it and continue.

After regenerating, update the commit SHA and date above, and re-run catalog's own test suite to confirm
nothing that reads the snapshot's specific IDs/values broke.
