# ruff: noqa: F401
from datagov_data_access.db.models import (
    Base,
    Dataset,
    DatasetViewCount,
    Error,
    HarvestJob,
    HarvestJobError,
    HarvestRecord,
    HarvestRecordError,
    HarvestSource,
    HarvestUser,
    Locations,
    Organization,
    ResourceViewCount,
)
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy(model_class=Base)
