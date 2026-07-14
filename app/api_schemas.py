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
from app.search import API_CONTEXT, FILTERS, ApiQueryParam
from shared.constants import ORGANIZATION_TYPE_VALUES

ORGANIZATION_TYPE_ENUM = PyEnum(
    "OrganizationType", [(a, a) for a in ORGANIZATION_TYPE_VALUES]
)
SORT_BY_ENUM = PyEnum(
    "SortBy",
    [(a, a) for a in ("relevance", "popularity", "distance", "last_harvested_date")],
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


def _api_enum(name: str, values: tuple[str, ...]):
    return PyEnum(name, [(value, value) for value in values])


def _api_query_field(param: ApiQueryParam):
    if param.enum_values:
        field = Enum(
            _api_enum(f"{param.name.title().replace('_', '')}Param", param.enum_values)
        )
    elif param.field_type == "boolean":
        field = Boolean()
    elif param.field_type == "json_string":
        field = String(
            metadata={"description": "URL-encoded JSON value, such as GeoJSON."}
        )
    else:
        field = String()

    if param.repeated:
        return List(field)
    return field


def _search_filter_query_fields():
    fields = {}
    for definition in FILTERS:
        if API_CONTEXT not in definition.parse_contexts:
            continue
        for param in definition.api_query_params:
            fields[param.name] = _api_query_field(param)
    return fields


def _build_search_query_schema():
    fields = {
        "q": String(),
        "sort": Enum(SORT_BY_ENUM),
        "per_page": Integer(
            validate=Range(min=1, max=SEARCH_API_MAX_PER_PAGE),
            metadata={
                "description": (
                    f"Number of results per page. Must be between 1 and "
                    f"{SEARCH_API_MAX_PER_PAGE}."
                )
            },
        ),
        "after": String(),
    }
    fields.update(_search_filter_query_fields())
    return type("SearchQuery", (Schema,), fields)


SearchQuery = _build_search_query_schema()


class KeywordsQuery(Schema):
    size = Integer()
    min_count = Integer()
    search = String()


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
