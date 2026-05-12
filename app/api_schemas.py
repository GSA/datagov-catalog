from enum import Enum as PyEnum

from apiflask import Schema
from apiflask.fields import (
    URL,
    UUID,
    Boolean,
    Date,
    Dict,
    Enum,
    Field,
    Float,
    Integer,
    List,
    Nested,
    String,
)
from apiflask.validators import Length, Range

from app.database.constants import SEARCH_API_MAX_PER_PAGE
from shared.constants import ORGANIZATION_TYPE_VALUES

ORGANIZATION_TYPE_ENUM = PyEnum(
    "OrganizationType", [(a, a) for a in ORGANIZATION_TYPE_VALUES]
)
SORT_BY_ENUM = PyEnum(
    "SortBy",
    [(a, a) for a in ("relevance", "popularity", "distance", "last_harvested_date")],
)
SPATIAL_FILTER_ENUM = PyEnum(
    "SpatialFilter", [(a, a) for a in ("geospatial", "non-geospatial")]
)


class Organization(Schema):
    aliases = List(String())
    description = String()
    id = UUID()
    logo = URL()
    name = String()
    slug = String()
    organization_type = Enum(ORGANIZATION_TYPE_ENUM)


class Centroid(Schema):
    lat = Float()
    lon = Float()


class GeoJson(Schema):
    coordinates = List(List(List(Float(), validate=Length(equal=2))))
    type = String()


class _Any(Field):
    pass


class Dataset(Schema):
    _score = Float()
    _sort = List(_Any())
    dcat = Dict()
    description = String()
    harvest_record = URL()
    harvest_record_raw = URL()
    harvest_record_transformed = URL()
    has_spatial = Boolean()
    identifier = String()
    keyword = List(String())
    last_harvested_date = Date()
    organization = Nested(Organization())
    popularity = Integer()
    publisher = String()
    slug = String()
    spatial_centroid = Centroid()
    spatial_shape = GeoJson()


class SearchResults(Schema):
    results = List(Nested(Dataset), required=True)
    sort = Enum(SORT_BY_ENUM, required=True)
    after = String(required=False)


class SearchQuery(Schema):
    q = String()
    sort = Enum(SORT_BY_ENUM)
    per_page = Integer(
        validate=Range(min=1, max=SEARCH_API_MAX_PER_PAGE),
        metadata={
            "description": (
                f"Number of results per page. Must be between 1 and "
                f"{SEARCH_API_MAX_PER_PAGE}."
            )
        },
    )
    org_slug = String()
    org_type = Enum(ORGANIZATION_TYPE_ENUM)
    keyword = List(String())
    publisher = String()
    after = String()
    spatial_filter = Enum(SPATIAL_FILTER_ENUM)
    spatial_feature = GeoJson()
    spatial_within = Boolean()


class KeywordsQuery(Schema):
    size = Integer()
    min_count = Integer()


class KeywordAndCount(Schema):
    keyword = String()
    count = Integer()


class KeywordsResults(Schema):
    keywords = List(Nested(KeywordAndCount))
    total = Integer()
    size = Integer()
    min_count = Integer()


class OrganizationResponse(Schema):
    id = UUID()
    name = String()
    slug = String()
    organization_type = Enum(ORGANIZATION_TYPE_ENUM)
    aliases = List(String())
    count = Integer()


class OrganizationsResults(Schema):
    organizations = List(Nested(OrganizationResponse))
    total = Integer()


class PublisherResponse(Schema):
    name = String()
    count = Integer()


class PublishersResults(Schema):
    publishers = List(Nested(PublisherResponse))
    total = Integer()


class OpensearchHealth(Schema):
    status = String()


class LocationsQuery(Schema):
    q = String()
    size = Integer()


class LocationResponse(Schema):
    display_name = String()
    id = UUID()


class LocationsResults(Schema):
    locations = List(Nested(LocationResponse))
    size = Integer()
    total = Integer()


class LocationDetail(Schema):
    id = UUID()
    geometry = Nested(GeoJson())


class LocationId(Schema):
    location_id = UUID()


class StatsMeta(Schema):
    date = String()


class StatsMetrics(Schema):
    datasetsBarMetric = String()
    orgBarMetric = String()


class StatsResults(Schema):
    datasets = Integer()
    datasetsWithIsPartOf = Integer()


class StatsResult(Schema):
    meta = Nested(StatsMeta)
    metrics = Nested(StatsMetrics)
    results = Nested(StatsResults)
