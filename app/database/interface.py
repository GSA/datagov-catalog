"""Local database interface mirroring datagov-harvester."""

from __future__ import annotations

import logging
from typing import Any

from app.models import HarvestRecord, db

logger = logging.getLogger(__name__)


class CatalogDBInterface:
    """Subset of harvester interface for read-only access."""

    def __init__(self, session=None):
        self.db = session or db.session

    def get_harvest_record(self, record_id: str) -> HarvestRecord | None:
        return self.db.query(HarvestRecord).filter_by(id=record_id).first()

    def list_success_harvest_record_ids(self, page: int = 1, per_page: int = 20) -> dict[str, Any]:
        page = max(page, 1)
        per_page = max(min(per_page, 100), 1)
        query = (
            self.db.query(HarvestRecord.id)
            .filter(HarvestRecord.status == "success")
            .order_by(HarvestRecord.id.asc())
        )
        total = query.count()
        items = (
            query
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
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
