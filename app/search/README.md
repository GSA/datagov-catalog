# search

Vendored verbatim from [GSA/datagov_data_access](https://github.com/GSA/datagov_data_access) at tag `1.1.0`
(commit `36d1440`), as part of streamlining catalog's reads to only what it needs
(GSA/data.gov#6211). Only import paths were rewritten (`datagov_data_access.search.*` -> `app.search.*`,
`datagov_data_access.shared.*` -> `shared.*`).

`writer.py`, `documents.py`, and `transforms.py` were deliberately **not** vendored — they are the
OpenSearch write path, which catalog never calls; harvester is the only writer to the index (see
GSA/data.gov#6209, where harvester vendored the same package for the same reason). `client.py` and
`config.py` are vendored because the read path (`reader.py`) depends on them to construct a client and
resolve the index mappings, not because catalog writes with them.

`queries/` (including `queries/filters/`) is vendored too, for the same reason as `reader.py`: it's the
query-building/filter/aggregation layer catalog's routes and `reader.py` depend on at module level.

`app/search/registry.py` (pre-existing, `criteria_url_for`) is unrelated to the vendored
`app/search/queries/registry.py` and will be renamed to remove the ambiguity in a follow-up commit that
wires catalog onto this vendored code.
