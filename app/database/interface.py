"""Local database interface mirroring datagov-harvester."""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any

from sqlalchemy import func, or_

from app.models import Dataset, HarvestRecord, Locations, Organization, db

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

    def total_datasets(self):
        """Count how many records in the database table."""
        return self.db.query(Dataset).count()

    def get_harvest_record(self, record_id: str) -> HarvestRecord | None:
        return self.db.query(HarvestRecord).filter_by(id=record_id).first()

    def search_datasets(
        self,
        query: str = "",
        keywords: list[str] = [],
        per_page=DEFAULT_PER_PAGE,
        org_id=None,
        org_types=None,
        spatial_filter=None,
        spatial_geometry=None,
        spatial_within=True,
        after=None,
        sort_by="relevance",
        *args,
        **kwargs,
    ):
        """Text search for datasets from the OpenSearch index.

        The query is in OpenSearch's "multi_match" search format where it analyzes
        the text and matches against multiple fields.

        per_page paginates results with this many entries. If org_id is
        specified, only datasets for that organization are searched. after is
        an encoded string that will be passed through to Opensearch for
        accessing further pages. spatial_filter can be "geospatial" or
        "non-geospatial" to filter by presence of spatial data.
        spatial_geometry and spatial_within allow searching geographically for
        datasets. See OpenSearchInterface.search for details.
        """
        if after is not None:
            search_after = SearchResult.decode_search_after(after)
        else:
            search_after = None
        return self.opensearch.search(
            query,
            keywords=keywords,
            per_page=per_page,
            org_id=org_id,
            org_types=org_types,
            search_after=search_after,
            spatial_filter=spatial_filter,
            spatial_geometry=spatial_geometry,
            spatial_within=spatial_within,
            sort_by=sort_by,
        )

    def get_unique_keywords(self, size=100, min_doc_count=1) -> list[dict]:
        """
        Get unique keywords from all datasets with their document counts.

        size: Maximum number of unique keywords to return (default 100)
        min_doc_count: Minimum number of documents a keyword must appear in (default 1)
        """
        return self.opensearch.get_unique_keywords(
            size=size, min_doc_count=min_doc_count
        )

    def search_locations(self, query, size=100):
        """
        Get locations from the database. These are in type_order with first
        countries, then states, then counties, finally postal codes.

        size: Maximum number of locations to return (default 100)
        """
        return (
            self.db.query(Locations)
            .filter(Locations.display_name.ilike(f"%{query}%"))
            .order_by(Locations.type_order)
            .limit(size)
        )

    def get_location(self, location_id):
        """
        Get information for a single location.

        Returns a tuple of (id, GeoJSON), or None if the location id doesn't exist.
        """
        return (
            self.db.query(Locations.id, func.ST_AsGeoJSON(Locations.the_geom))
            .filter(Locations.id == location_id)
            .first()
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
                    func.array_to_string(Organization.aliases, ",").ilike(like_pattern),
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

        open_search_dataset_counts = self.get_opensearch_org_dataset_counts(
            as_dict=True
        )

        for item in items:
            item.dataset_count = open_search_dataset_counts.get(item.slug, 0)

        return {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "organizations": [
                {
                    **self.to_dict(item),
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

    def list_datasets_for_organization(
        self,
        organization_id: str,
        sort_by: str | None = "relevance",
        dataset_search_query: str = "",
        num_results=DEFAULT_PER_PAGE,
        keywords: list[str] | None = None,
        spatial_filter: str | None = None,
        spatial_geometry: dict | None = None,
        spatial_within: bool = True,
    ) -> SearchResult:
        if not organization_id:
            return SearchResult.empty()

        return self.search_datasets(
            dataset_search_query,
            keywords=keywords or [],
            org_id=organization_id,
            sort_by=sort_by,
            per_page=num_results,
            spatial_filter=spatial_filter,
            spatial_geometry=spatial_geometry,
            spatial_within=spatial_within,
        )

    def get_opensearch_org_dataset_counts(self, as_dict=False):
        """
        get all organization dataset counts. used in /organization
        """
        # we already ignore empty orgs
        base_query = self._organization_query(ignore_empty_orgs=True)
        total = base_query.count()

        # ensure the requested size is always slightly bigger than what we have
        return self.opensearch.get_organization_counts(size=total + 1, as_dict=as_dict)

    def get_top_organizations(self, limit: int = 10) -> list[dict]:
        """Return organizations ordered by dataset count, using OpenSearch counts."""
        limit = max(min(limit, 100), 1)

        try:
            org_counts = self.opensearch.get_organization_counts(size=limit)
        except Exception:
            logger.exception("Failed to fetch organization counts from OpenSearch")
            return self._get_top_organizations_from_db(limit)

        if not org_counts:
            return self._get_top_organizations_from_db(limit)

        slugs = [entry["slug"] for entry in org_counts if entry.get("slug")]
        if not slugs:
            return self._get_top_organizations_from_db(limit)

        organizations = (
            self.db.query(Organization).filter(Organization.slug.in_(slugs)).all()
        )
        org_by_slug = {org.slug: org for org in organizations}

        hydrated: list[dict] = []
        for entry in org_counts:
            slug = entry.get("slug")
            if not slug:
                continue
            org = org_by_slug.get(slug)
            if not org:
                continue
            hydrated.append(
                {
                    "id": org.id,
                    "name": org.name,
                    "slug": org.slug,
                    "organization_type": org.organization_type,
                    "dataset_count": entry.get("count", 0),
                    "aliases": org.aliases or [],
                }
            )

        if hydrated:
            return hydrated

        return self._get_top_organizations_from_db(limit)

    def _get_top_organizations_from_db(self, limit: int) -> list[dict]:
        rows = (
            self.db.query(
                Organization.id,
                Organization.name,
                Organization.slug,
                Organization.organization_type,
                Organization.aliases,
                func.count(Dataset.id).label("dataset_count"),
            )
            .join(Dataset, Dataset.organization_id == Organization.id)
            .group_by(
                Organization.id,
                Organization.name,
                Organization.slug,
                Organization.organization_type,
                Organization.aliases,
            )
            .order_by(func.count(Dataset.id).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": row.id,
                "name": row.name,
                "slug": row.slug,
                "organization_type": row.organization_type,
                "dataset_count": row.dataset_count,
                "aliases": row.aliases or [],
            }
            for row in rows
        ]

    @staticmethod
    def to_dict(obj: Any) -> dict[str, Any] | None:
        if obj is None:
            return None

        data_dict = obj.to_dict()

        # check for any additional temporary attributes
        if getattr(obj, "dataset_count"):
            data_dict["dataset_count"] = obj.dataset_count

        return data_dict

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

    def count_all_datasets_in_search(self) -> int:
        """
        Get the total number of datasets from our index
        """
        return self.opensearch.count_all_datasets()
