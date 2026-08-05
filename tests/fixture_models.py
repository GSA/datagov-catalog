"""Write-only model for a table catalog never reads.

`app.models` deliberately has no `HarvestJob` -- catalog never queries it (see
GSA/data.gov#6211). But harvester's real schema still has a non-nullable,
FK-enforced `harvest_record.harvest_job_id -> harvest_job.id`, and datagov-harvester's
"Catalog Contract" test (GSA/data.gov#6210) runs these fixtures against that real
schema, not catalog's own FK-less one. Without a real `harvest_job` row, inserting
a `HarvestRecord` there fails on the foreign key, even though it succeeds silently
against catalog's own schema.

This model exists only so fixtures can write a row satisfying that FK. It's not
exported from app.models and nothing in app/ imports it.

All of harvester's real harvest_job columns are declared (not just the two fixtures
actually set) so that tests/data/harvester_snapshot/postgres.sql's COPY statement --
which lists every column pg_dump found on the real table -- loads without an
UndefinedColumn error under catalog's own db.create_all() schema.
"""

from sqlalchemy import Column, DateTime, Integer, String

from app.models import Base


class HarvestJobFixtureModel(Base):
    __tablename__ = "harvest_job"

    harvest_source_id = Column(String(36))
    status = Column(String)
    job_type = Column(String(20))
    date_created = Column(DateTime)
    date_finished = Column(DateTime)
    records_total = Column(Integer)
    records_added = Column(Integer)
    records_updated = Column(Integer)
    records_deleted = Column(Integer)
    records_errored = Column(Integer)
    records_warned = Column(Integer)
    records_ignored = Column(Integer)
    records_validated = Column(Integer)
