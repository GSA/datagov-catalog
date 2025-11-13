"""Local database interface mirroring datagov-harvester."""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any

from sqlalchemy import desc, func, or_

from app.models import Dataset, HarvestRecord, Organization, db

from .constants import DEFAULT_PAGE, DEFAULT_PER_PAGE
from .opensearch import OpenSearchInterface, SearchResult

logger = logging.getLogger(__name__)


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
        self.opensearch = OpenSearchInterface.from_environment()

    def get_harvest_record(self, record_id: str) -> HarvestRecord | None:
        return self.db.query(HarvestRecord).filter_by(id=record_id).first()

    def search_datasets(
        self,
        query: str,
        per_page=DEFAULT_PER_PAGE,
        org_id=None,
        after=None,
        *args,
        **kwargs,
    ):
        """Text search for datasets from the OpenSearch index.

        The query is in OpenSearch's "multi_match" search format where it analyzes
        the text and matches against multiple fields.

        per_page paginates results with this many entries. If org_id is
        specified, only datasets for that organization are searched. after is
        an encoded string that will be passed through to Opensearch for
        accessing further pages.
        """
        if after is not None:
            search_after = SearchResult.decode_search_after(after)
        else:
            search_after = None
        sort_by = kwargs.get("sort_by", "relevance")
        return self.opensearch.search(
            query,
            per_page=per_page,
            org_id=org_id,
            search_after=search_after,
            sort_by=sort_by,
        )

    def _postgres_search_datasets(self, query: str, include_org=False, *args, **kwargs):
        """Text search for datasets.

        Use the `query` to find matching datasets. The query is in Postgres's
        "websearch" format which allows the use of quoted phrases with AND
        and OR keywords.

        include_org
            include org with dataset
        """
        # default sort to relevance
        sort_by = kwargs.get("sort_by", "relevance").lower()
        ts_query = func.websearch_to_tsquery("english", query)

        query = (
            self.db.query(Dataset, Organization)
            if include_org
            else self.db.query(Dataset)
        )

        query = query.filter(Dataset.search_vector.op("@@")(ts_query))

        if include_org:
            query = query.join(Organization, Dataset.organization_id == Organization.id)

            # we only want to filter by org type if we include the org join
            if kwargs.get("org_types"):
                org_types = kwargs["org_types"]
                query = query.filter(Organization.organization_type.in_(org_types))

        if sort_by == "relevance":
            return query.order_by(
                desc(
                    func.ts_rank(
                        Dataset.search_vector,
                        ts_query,
                    )
                )
            )

    def _success_harvest_record_ids_query(self):
        return (
            self.db.query(HarvestRecord.id)
            .filter(HarvestRecord.status == "success")
            .order_by(HarvestRecord.id.asc())
        )

    def _organization_query(
        self, search: str | None = None, ignore_empty_orgs: bool = False
    ):
        """
        query organizations based on [search].

        ignore_empty_orgs
            omit organizations which have 0 datasets
        """
        query = self.db.query(Organization)

        if ignore_empty_orgs:
            query = (
                self.db.query(Organization)
                .outerjoin(Organization.datasets)
                .group_by(Organization.id)
                .having(func.count(Dataset.id) > 0)
            )

        if search:
            like_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Organization.name.ilike(like_pattern),
                    Organization.slug.ilike(like_pattern),
                    Organization.description.ilike(like_pattern),
                )
            )
        return query.order_by(Organization.name.asc())

    @paginate
    def _organization_paginated(
        self, search: str | None = None, ignore_empty_orgs: bool = False, **kwargs
    ):
        return self._organization_query(
            search=search, ignore_empty_orgs=ignore_empty_orgs
        )

    def list_organizations(
        self,
        page: int = 1,
        per_page: int = DEFAULT_PER_PAGE,
        search: str | None = None,
        ignore_empty_orgs: bool = False,
    ) -> dict[str, Any]:
        page = max(page, 1)
        per_page = max(min(per_page, 100), 1)
        base_query = self._organization_query(
            search=search, ignore_empty_orgs=ignore_empty_orgs
        )
        total = base_query.count()
        items = self._organization_paginated(
            page=page,
            per_page=per_page,
            search=search,
            ignore_empty_orgs=ignore_empty_orgs,
        )
        total_pages = max(((total + per_page - 1) // per_page), 1)

        dataset_counts: dict[str, int] = {}
        organization_ids = [item.id for item in items]
        if organization_ids:
            counts = (
                self.db.query(Dataset.organization_id, func.count(Dataset.id))
                .filter(Dataset.organization_id.in_(organization_ids))
                .group_by(Dataset.organization_id)
                .all()
            )
            dataset_counts = {org_id: count for org_id, count in counts}

        return {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "organizations": [
                {
                    **self.to_dict(item),
                    "dataset_count": dataset_counts.get(item.id, 0),
                }
                for item in items
            ],
            "search": search or "",
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

    def _datasets_for_organization_query(
        self,
        organization_id: str,
        sort_by: str | None = None,
        dataset_search_terms: str = "",
    ):
        query = self.db.query(Dataset).filter(
            Dataset.organization_id == organization_id
        )

        if dataset_search_terms:
            query = self._postgres_search_datasets(dataset_search_terms).filter(
                Dataset.organization_id == organization_id
            )

        sort_key = (sort_by or "popularity").lower()

        if sort_key == "slug":
            order_by = [Dataset.slug.asc()]
        elif sort_key == "harvested":
            order_by = [
                Dataset.last_harvested_date.desc().nullslast(),
                Dataset.slug.asc(),
            ]
        else:
            # Default to popularity, highest first with slug tie-breaker
            order_by = [Dataset.popularity.desc().nullslast(), Dataset.slug.asc()]

        return query.order_by(*order_by)

    @paginate
    def _datasets_for_organization_paginated(
        self,
        organization_id: str,
        sort_by: str | None = None,
        dataset_search_terms: str = "",
        **kwargs,
    ):
        return self._datasets_for_organization_query(
            organization_id, sort_by=sort_by, dataset_search_terms=dataset_search_terms
        )

    def list_datasets_for_organization(
        self,
        organization_id: str,
        page: int = DEFAULT_PAGE,
        per_page: int = DEFAULT_PER_PAGE,
        sort_by: str | None = None,
        dataset_search_terms: str = "",
    ) -> dict[str, Any]:
        allowed_sorts = {"popularity", "slug", "harvested"}
        sort_key = (sort_by or "popularity").lower()
        if sort_key == "published":
            sort_key = "harvested"
        if sort_key not in allowed_sorts:
            sort_key = "popularity"

        if not organization_id:
            return {
                "page": DEFAULT_PAGE,
                "per_page": DEFAULT_PER_PAGE,
                "total": 0,
                "total_pages": 0,
                "datasets": [],
                "sort": sort_key,
            }

        page = max(page, 1)
        per_page = max(min(per_page, 100), 1)

        base_query = self._datasets_for_organization_query(
            organization_id,
            sort_by=sort_key,
            dataset_search_terms=dataset_search_terms,
        )
        total = base_query.count()
        datasets = self._datasets_for_organization_paginated(
            organization_id,
            page=page,
            per_page=per_page,
            sort_by=sort_key,
            dataset_search_terms=dataset_search_terms,
        )

        total_pages = (total + per_page - 1) // per_page if total else 0

        return {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "datasets": [self.to_dict(dataset) for dataset in datasets],
            "sort": sort_key,
        }

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

    def get_dataset_by_slug(self, dataset_slug: str) -> Dataset | None:
        """
        Get dataset by its slug. If the slug is not found, return None.
        """
        return self.db.query(Dataset).filter_by(slug=dataset_slug).first()

    def get_dataset_by_id(self, dataset_id: str) -> Dataset | None:
        """
        Get dataset by its guid. If the ID is not found, return None.
        """
        return self.db.query(Dataset).filter_by(id=dataset_id).first()
