"""Local database interface mirroring datagov-harvester."""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any

from sqlalchemy import func, or_

from app.models import Dataset, HarvestRecord, Organization, db

logger = logging.getLogger(__name__)

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


class CatalogDBInterface:
    """Subset of harvester interface for read-only access."""

    def __init__(self, session=None):
        self.db = session or db.session

    def get_harvest_record(self, record_id: str) -> HarvestRecord | None:
        return self.db.query(HarvestRecord).filter_by(id=record_id).first()

    @paginate
    def search_datasets(self, query: str, *args, **kwargs):
        """Text search for datasets.

        Use the `query` to find matching datasets. The query is in Postgres's
        "websearch" format which allows the use of quoted phrases with AND
        and OR keywords.
        """
        return (
            self.db.query(Dataset)
            .filter(Dataset.search_vector.op("@@")(func.websearch_to_tsquery(query)))
            .order_by(
                func.ts_rank(Dataset.search_vector, func.websearch_to_tsquery(query))
            )
        )

    def _success_harvest_record_ids_query(self):
        return (
            self.db.query(HarvestRecord.id)
            .filter(HarvestRecord.status == "success")
            .order_by(HarvestRecord.id.asc())
        )

    @paginate
    def _success_harvest_record_ids_paginated(self, **kwargs):
        return self._success_harvest_record_ids_query()

    def list_success_harvest_record_ids(
        self, page: int = 1, per_page: int = DEFAULT_PER_PAGE
    ) -> dict[str, Any]:
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

    def _organization_query(self):
        return self.db.query(Organization).order_by(Organization.name.asc())

    @paginate
    def _organization_paginated(self, **kwargs):
        return self._organization_query()

    def list_organizations(
        self, page: int = 1, per_page: int = DEFAULT_PER_PAGE
    ) -> dict[str, Any]:
        page = max(page, 1)
        per_page = max(min(per_page, 100), 1)
        base_query = self._organization_query()
        total = base_query.count()
        items = self._organization_paginated(page=page, per_page=per_page)
        total_pages = max(((total + per_page - 1) // per_page), 1)
        return {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "organizations": [self.to_dict(item) for item in items],
        }

    def get_organization_by_slug(self, slug: str) -> Organization | None:
        if not slug:
            return None
        return self.db.query(Organization).filter(Organization.slug == slug).first()

    def get_organization_by_id(self, organization_id: str) -> Organization | None:
        if not organization_id:
            return None
        return (
            self.db.query(Organization)
            .filter(Organization.id == organization_id)
            .first()
        )

    @staticmethod
    def to_dict(obj: Any) -> dict[str, Any] | None:
        if obj is None:
            return None

        return obj.to_dict()

    def search_harvest_records(
        self,
        query: str | None = None,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """
        Search harvest records with optional filters.

        query: Search term to match against identifier, ckan_id, ckan_name,
        and source_raw fields.
        status: Filter by status ('success' or 'error')
        page: Page number (starts at 1)
        per_page: Number of results per page (max 100)

        Dict with pagination info and list of harvest records
        """
        page = max(page, 1)
        per_page = max(min(per_page, 50), 1)

        db_query = self.db.query(HarvestRecord)

        if query:
            # Use ilike for case-insensitive search
            search_pattern = f"%{query}%"
            db_query = db_query.filter(
                or_(
                    HarvestRecord.identifier.ilike(search_pattern),
                    HarvestRecord.ckan_id.ilike(search_pattern),
                    HarvestRecord.ckan_name.ilike(search_pattern),
                )
            )

        if status:
            db_query = db_query.filter(HarvestRecord.status == status)

        db_query = db_query.order_by(HarvestRecord.date_created.desc())

        total = db_query.count()

        items = db_query.offset((page - 1) * per_page).limit(per_page).all()

        return {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
            "records": [self.to_dict(record) for record in items],
        }
