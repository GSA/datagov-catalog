"""Local, read-only models for the tables catalog actually queries.

Slimmed from datagov_data_access.db.models (the harvester-owned schema) as
part of GSA/data.gov#6211. Foreign keys, check constraints, and Postgres
Enum types are deliberately dropped: catalog never writes to these tables,
so FKs/constraints buy nothing, and an Enum whose value set drifts from
harvester's raises LookupError on *read* for any row using the new value.
Columns are otherwise kept in full to preserve Base.to_dict() output shape.
"""

import uuid

from flask_sqlalchemy import SQLAlchemy
from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import DeclarativeBase, backref, column_property, relationship
from sqlalchemy.sql import select


class Base(DeclarativeBase):
    __abstract__ = True
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class Organization(Base):
    __tablename__ = "organization"

    name = Column(String, nullable=False, index=True)
    logo = Column(String)
    description = Column(Text)
    slug = Column(String(100), nullable=False)
    organization_type = Column(String)
    aliases = Column(ARRAY(String))


class HarvestSource(Base):
    """Only exists for Organization.source_count and the /api/stats count."""

    __tablename__ = "harvest_source"

    organization_id = Column(String(36), index=True)
    name = Column(String)
    url = Column(String)
    notification_emails = Column(ARRAY(String))
    frequency = Column(String)
    schema_type = Column(String)
    source_type = Column(String)
    notification_frequency = Column(String)
    collection_parent_url = Column(String)


Organization.source_count = column_property(
    select(func.count(HarvestSource.id))
    .where(HarvestSource.organization_id == Organization.id)
    .correlate_except(HarvestSource)
    .scalar_subquery()
)


class HarvestRecord(Base):
    __tablename__ = "harvest_record"

    identifier = Column(String, nullable=False)
    harvest_job_id = Column(String(36), index=True)
    harvest_source_id = Column(String(36), index=True)
    source_hash = Column(String)
    source_raw = Column(String)
    source_transform = Column(JSONB)
    date_created = Column(DateTime, index=True, default=func.statement_timestamp())
    date_finished = Column(DateTime, index=True)
    ckan_id = Column(String, index=True)
    action = Column(String, index=True)
    parent_identifier = Column(String)
    status = Column(String, index=True)


class Dataset(Base):
    __tablename__ = "dataset"

    slug = Column(String, nullable=False, index=True, unique=True)
    dcat = Column(MutableDict.as_mutable(JSONB), nullable=False)
    translated_spatial = Column(JSONB)
    organization_id = Column(String(36), index=True)
    harvest_source_id = Column(String(36), index=True)
    harvest_record_id = Column(String(36), index=True, unique=True)
    popularity = Column(Integer, server_default="0")
    last_harvested_date = Column(DateTime, index=True)

    organization = relationship(
        "Organization",
        backref=backref("datasets", lazy=True),
        primaryjoin="Dataset.organization_id == Organization.id",
        foreign_keys=[organization_id],
        lazy="joined",
        viewonly=True,
    )

    # Not read anywhere in catalog's own code, but needed for
    # dataset.harvest_record.source_transform in the (still library-owned,
    # unvendored) OpenSearch write path used by tests and `flask search compare`.
    harvest_record = relationship(
        "HarvestRecord",
        primaryjoin="Dataset.harvest_record_id == HarvestRecord.id",
        foreign_keys=[harvest_record_id],
        uselist=False,
        viewonly=True,
    )


class Locations(Base):
    __tablename__ = "locations"

    name = Column(String)
    type = Column(String)
    display_name = Column(String)
    the_geom = Column(Geometry(geometry_type="MULTIPOLYGON"))
    type_order = Column(Integer)


db = SQLAlchemy(model_class=Base)
