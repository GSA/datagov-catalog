"""Load the committed harvester snapshot into catalog's test Postgres/OpenSearch.

See tests/data/harvester_snapshot/README.md for what this is and how to regenerate it.
Parses pg_dump's own COPY-block format directly (no `psql` binary required) and streams
each block through psycopg's native COPY support.
"""

import json
import re
from pathlib import Path

SNAPSHOT_DIR = Path(__file__).parent / "data" / "harvester_snapshot"

_COPY_BLOCK = re.compile(
    r"^COPY (public\.\w+) \(([^)]+)\) FROM stdin;\n(.*?)\n\\\.$",
    re.MULTILINE | re.DOTALL,
)


def load_postgres_snapshot(connection) -> None:
    """Load tests/data/harvester_snapshot/postgres.sql into the given DB-API connection."""
    sql = (SNAPSHOT_DIR / "postgres.sql").read_text()
    with connection.cursor() as cursor:
        for table, columns, data in _COPY_BLOCK.findall(sql):
            if not data:
                continue
            with cursor.copy(f"COPY {table} ({columns}) FROM STDIN") as copy:
                copy.write(data + "\n")
    connection.commit()


def load_opensearch_snapshot(opensearch_client) -> None:
    """Bulk-index tests/data/harvester_snapshot/opensearch.ndjson into the given client."""
    lines = (SNAPSHOT_DIR / "opensearch.ndjson").read_text().strip().splitlines()
    actions = [json.loads(line) for line in lines]
    if not actions:
        return
    body = "\n".join(json.dumps(action) for action in actions) + "\n"
    opensearch_client.bulk(body=body, refresh=True)
