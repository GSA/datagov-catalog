"""Which OpenSearchWriter implementation the test suite indexes through.

In production, harvester writes the OpenSearch documents and catalog only reads
them. Catalog owns no part of the write path and never defines the index schema.

Catalog's own test suite, though, has to get documents into the index somehow, and
by default it uses catalog's vendored `app.search.writer.OpenSearchWriter`. That is
a closed loop: catalog writes documents with its own copy of the writer, then reads
them back with its own reader, so a harvester-side change to `DatasetDocument`,
`MAPPINGS`, or the writer cannot be detected. Fine for catalog's own CI, useless as
a cross-repo contract check.

Setting `HARVESTER_SEARCH_PATH` to a checkout of harvester's `search/` package makes
this module return *harvester's* writer instead. datagov-harvester's "Catalog
Contract" job does exactly that, so catalog's full fixture set -- DCAT-US 3.0 rows,
isPartOf collections, spatial bboxes, stopword titles -- gets indexed by harvester's
real production write path and read back by catalog's real production read path.
Neither side is faked or substituted. See GSA/data.gov#6210.

This is deliberately *not* the file-overlay approach that was removed from that job:
nothing in `app/search/` is clobbered, no filename parity between the two repos is
required, and harvester adding a module catalog lacks is a non-event. Harvester's
code is imported under its own namespace and only the writer is swapped.

`index_datasets(iterable_of_dataset_rows)` is the entire contract. Harvester's writer
is duck-typed and reads a fixed set of attributes off whatever it is handed -- dcat,
id, slug, organization, popularity, translated_spatial, harvest_record_id,
last_harvested_date -- all of which catalog's slim `app.models.Dataset` provides.
"""

import importlib
import os
import sys
from pathlib import Path

ENV_VAR = "HARVESTER_SEARCH_PATH"


def _load_harvester_writer(search_path: str):
    """Import harvester's OpenSearchWriter from a checkout of its `search/` package.

    Harvester's modules import each other as `search.*` and read
    `shared.constants`, so the *parent* of the search directory goes on sys.path
    and the package keeps its own name. Nothing is copied over `app/search/`.
    """
    package_dir = Path(search_path)
    if not (package_dir / "writer.py").is_file():
        raise RuntimeError(
            f"{ENV_VAR}={search_path!r} does not look like harvester's search/ "
            "package: no writer.py found. Mount harvester's search/ directory there."
        )

    parent = str(package_dir.parent.resolve())
    if parent not in sys.path:
        sys.path.insert(0, parent)

    module = importlib.import_module(f"{package_dir.name}.writer")
    try:
        return module.OpenSearchWriter
    except AttributeError as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            f"{package_dir.name}.writer has no OpenSearchWriter; harvester's write "
            "path was renamed and this contract hook needs updating."
        ) from exc


def resolve_writer_class():
    """Return the writer class the suite should index through.

    Harvester's if HARVESTER_SEARCH_PATH is set, otherwise catalog's own.
    """
    search_path = os.getenv(ENV_VAR)
    if not search_path:
        from app.search.writer import OpenSearchWriter

        return OpenSearchWriter

    return _load_harvester_writer(search_path)


def writer_origin():
    """Human-readable description of which writer is in use, for test output."""
    search_path = os.getenv(ENV_VAR)
    return (
        f"harvester ({search_path})" if search_path else "catalog (app.search.writer)"
    )
