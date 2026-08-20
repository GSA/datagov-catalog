# search

Vendored verbatim from [GSA/datagov_data_access](https://github.com/GSA/datagov_data_access) at tag `1.1.0`
(commit `36d1440`), as part of streamlining catalog's reads to only what it needs
(GSA/data.gov#6211). Only import paths were rewritten (`datagov_data_access.search.*` -> `app.search.*`,
`datagov_data_access.shared.*` -> `shared.*`, `datagov_data_access.db.models` -> `app.models`).

`client.py`, `config.py`, `mappings.py`, `reader.py`, `spatial.py`, and `queries/` (including
`queries/filters/`) are the OpenSearch **read** path: what catalog's own routes and templates call at
request time.

`writer.py`, `documents.py`, and `transforms.py` are the OpenSearch **write** path. Catalog is read-only in
production — harvester is the sole writer to the real index (see GSA/data.gov#6209, where harvester
vendored the same package for the same reason) — but catalog's own dev/CI tooling still needs to build and
write documents:

- `flask search compare --update` (`app/commands.py`), which `make load-test-data` calls to reindex a local
  OpenSearch from fixture data.
- `tests/unit/conftest.py`'s `opensearch_writer` fixture, which indexes fixture/edge-case datasets so
  search/filter tests have something to query.

These were vendored (rather than left as a dependency on `datagov-data-access`) so catalog has zero
dependency on that package, which is itself expected to be deprecated once GSA/data.gov#6209 folds it back
into harvester.

`writer.py`'s `index_dataset_batches` queries `app.models.Dataset` directly (not just a type hint), which
is what makes this vendored copy diverge in *behavior*, not just import path, from the original: it now
indexes against catalog's own slim `Dataset` model instead of harvester's full one. `documents.py` reads
`dataset.organization`, `dataset.harvest_record.source_transform`, `dataset.translated_spatial`, etc. via
plain attribute access, so it works against the slim models without any further changes -- see
`app/models.py` for why `Dataset.harvest_record` is kept as a relationship despite nothing in catalog's own
route code touching it.
