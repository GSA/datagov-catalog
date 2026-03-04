from enum import Enum as PyEnum

from apiflask import Schema
from apiflask.fields import (
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
    URL,
    UUID,
)
from apiflask.validators import Length, Range

from shared.constants import ORGANIZATION_TYPE_VALUES

ORGANIZATION_TYPE_ENUM = PyEnum(
    "OrganizationType", [(a, a) for a in ORGANIZATION_TYPE_VALUES]
)
SORT_BY_ENUM = PyEnum(
    "SortBy", [(a, a) for a in ("relevance", "popularity", "distance")]
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
    sort_by = Enum(SORT_BY_ENUM)
    per_page = Integer(validate=Range(min=1))
    org_slug = String()
    org_type = Enum(ORGANIZATION_TYPE_ENUM)
    keyword = List(String())
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


class OrganizationsQuery(Schema):
    size = Integer()


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
    size = Integer()


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
