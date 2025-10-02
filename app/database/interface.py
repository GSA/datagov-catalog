"""Local database interface mirroring datagov-harvester."""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any
DEFAULT_PER_PAGE = 20
DEFAULT_PAGE = 1


def paginate(fn):
    @wraps(fn)
    def _impl(self, *args, **kwargs):
        query = fn(self, *args, **kwargs)
        if kwargs.get("count") is True:
            return query
        if kwargs.get("paginate") is False:
            return query.all()

        per_page = kwargs.get("per_page") or DEFAULT_PER_PAGE
        page = kwargs.get("page") or DEFAULT_PAGE

        per_page = max(min(per_page, 100), 1)
        page = max(page, 1)

        query = query.limit(per_page)
        query = query.offset((page - 1) * per_page)
        return query.all()

    return _impl

from app.models import HarvestRecord, db

logger = logging.getLogger(__name__)


class CatalogDBInterface:
    """Subset of harvester interface for read-only access."""

    def __init__(self, session=None):
        self.db = session or db.session

    def get_harvest_record(self, record_id: str) -> HarvestRecord | None:
        return self.db.query(HarvestRecord).filter_by(id=record_id).first()

    def _success_harvest_record_ids_query(self):
        return (
            self.db.query(HarvestRecord.id)
            .filter(HarvestRecord.status == "success")
            .order_by(HarvestRecord.id.asc())
        )

    @paginate
    def _success_harvest_record_ids_paginated(self, **kwargs):
        return self._success_harvest_record_ids_query()

    def list_success_harvest_record_ids(self, page: int = 1, per_page: int = DEFAULT_PER_PAGE) -> dict[str, Any]:
        page = max(page, 1)
        per_page = max(min(per_page, 100), 1)
        base_query = self._success_harvest_record_ids_query()
        total = base_query.count()
        items = self._success_harvest_record_ids_paginated(page=page, per_page=per_page)
        return {
            "page": page,
            "per_page": per_page,
            "total": total,
            "ids": [item.id for item in items],
        }

    @staticmethod
    def to_dict(obj: Any) -> dict[str, Any] | None:
        if obj is None:
            return None

        return obj.to_dict()
