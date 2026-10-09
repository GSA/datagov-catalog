import copy
import json
import uuid
from typing import Any, TypedDict

import factory
from factory import random as factory_random

from app.models import Dataset, HarvestRecord, HarvestSource, Organization

from .fixtures import DEFAULT_LAST_HARVESTED_DATE

FIXED_TEST_DATA_SEED = 1

ACCESS_PROFILES = (
    {"accessLevel": "public"},
    {"accessLevel": "non-public"},
    {"accessLevel": "restricted public"},
    {"accessRights": "public"},
    {"accessRights": "restricted"},
    {},
)

RESOURCE_FORMATS = (
    {"format": "CSV"},
    {"mediaType": "application/json"},
    {"downloadURL": "data.geojson?download=1"},
    {
        "format": "XLSX",
        "mediaType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
    {"format": "PDF", "downloadURL": "https://example.gov/data/report.pdf"},
    {"format": "KML", "accessURL": "https://example.gov/data/map.kml"},
    {"mediaType": "application/vnd.unknown-format"},
    {},
    {
        "format": "application/x-netcdf",
        "downloadURL": "https://example.gov/data/climate.nc",
    },
    {"downloadURL": "https://example.gov/data/archive.zip"},
)

TOPIC_PROFILES = (
    (
        "transit",
        "Transit Ridership",
        ["public transit", "ridership", "transportation", "commuting"],
        "Transportation",
    ),
    (
        "climate",
        "Climate Observations",
        ["climate", "temperature", "weather", "environment"],
        "Climate and Environment",
    ),
    (
        "public-health",
        "Community Health Indicators",
        ["public health", "healthcare", "community health", "wellbeing"],
        "Health",
    ),
    (
        "education",
        "Education Outcomes",
        ["education", "schools", "students", "attainment"],
        "Education",
    ),
    (
        "housing",
        "Housing Affordability",
        ["housing", "rent", "affordability", "neighborhoods"],
        "Housing and Community Development",
    ),
    (
        "workforce",
        "Workforce Participation",
        ["workforce", "employment", "labor", "occupation"],
        "Employment",
    ),
    (
        "energy",
        "Energy Consumption",
        ["energy", "electricity", "renewables", "consumption"],
        "Energy",
    ),
    (
        "agriculture",
        "Agricultural Production",
        ["agriculture", "crops", "farms", "food systems"],
        "Agriculture",
    ),
    (
        "emergency",
        "Emergency Response",
        ["emergency management", "disaster response", "preparedness", "recovery"],
        "Public Safety",
    ),
    (
        "demographics",
        "Population Estimates",
        ["demographics", "population", "census", "communities"],
        "Population and Demographics",
    ),
    (
        "public-finance",
        "Public Expenditures",
        ["public finance", "budget", "expenditures", "government spending"],
        "Government Operations",
    ),
    (
        "water",
        "Water Quality Monitoring",
        ["water quality", "watersheds", "monitoring", "conservation"],
        "Natural Resources",
    ),
)


class FactoryFixtureData(TypedDict):
    organizations: list[Organization]
    harvest_sources: list[HarvestSource]
    harvest_records: list[HarvestRecord]
    datasets: list[Dataset]


class OrganizationFactory(factory.Factory):
    class Meta:
        model = Organization

    id = factory.Faker("uuid4")
    name = factory.Faker("company")
    slug = factory.Sequence(lambda n: f"generated-org-{n + 1}")
    organization_type = factory.Faker(
        "random_element",
        elements=("Federal Government", "State Government", "Local Government"),
    )
    aliases = factory.LazyFunction(list)


class HarvestSourceFactory(factory.Factory):
    class Meta:
        model = HarvestSource

    id = factory.Faker("uuid4")
    name = factory.Faker("company")
    organization_id = "organization-1"
    url = factory.Faker("url")
    frequency = "daily"
    schema_type = "dcatus1.1"
    source_type = "document"
    notification_frequency = "always"


class HarvestRecordFactory(factory.Factory):
    class Meta:
        model = HarvestRecord

    id = factory.Faker("uuid4")
    identifier = factory.Faker("slug")
    harvest_job_id = "1"
    harvest_source_id = "source-1"
    source_raw = "{}"
    source_transform = factory.LazyFunction(dict)


class DatasetFactory(factory.Factory):
    class Meta:
        model = Dataset

    id = factory.Faker("uuid4")
    slug = factory.Sequence(lambda n: f"generated-dataset-{n + 1}")
    dcat = factory.LazyFunction(
        lambda: {
            "@type": "dcat:Dataset",
            "title": "Generated test dataset",
            "accessLevel": "public",
            "distribution": [],
        }
    )
    organization_id = "organization-1"
    harvest_source_id = "source-1"
    harvest_record_id = "record-1"
    popularity = 0
    last_harvested_date = DEFAULT_LAST_HARVESTED_DATE


class DistributionFactory(factory.DictFactory):
    title = "Supplemental test resource"
    format = None
    mediaType = None
    downloadURL = None
    accessURL = None
    license = None


def _supplemental_distribution(
    dataset_index: int, resource_index: int
) -> dict[str, Any]:
    profile = RESOURCE_FORMATS[(dataset_index + resource_index) % len(RESOURCE_FORMATS)]
    resource = DistributionFactory.build(
        title=f"Supplemental resource {resource_index + 1} for dataset {dataset_index + 1}",
        **profile,
    )
    return {
        "@type": "dcat:Distribution",
        **{key: value for key, value in resource.items() if value is not None},
    }


def _enrich_dataset_metadata(
    dcat: dict[str, Any], dataset_index: int, *, include_spatial: bool = True
) -> dict[str, Any]:
    result = copy.deepcopy(dcat)

    if "accessLevel" not in result and "accessRights" not in result:
        result.update(
            ACCESS_PROFILES[
                (dataset_index + FIXED_TEST_DATA_SEED) % len(ACCESS_PROFILES)
            ]
        )

    if "theme" not in result:
        theme_index = dataset_index % 5
        if theme_index == 0:
            result["theme"] = ["National Service", "Community Development"]
        elif theme_index == 1:
            result["theme"] = [
                {"prefLabel": "Public Health", "inScheme": "test-scheme"}
            ]
        elif theme_index == 2:
            result["theme"] = "Economic Opportunity"
        elif theme_index == 3:
            result["theme"] = []

    if "temporal" not in result and dataset_index % 4 != 0:
        if dataset_index % 4 == 1:
            result["temporal"] = "2020-01-01/2024-12-31"
        elif dataset_index % 4 == 2:
            result["temporal"] = {
                "startDate": "2020-01-01",
                "endDate": "2024-12-31",
            }
        else:
            result["temporal"] = "2024"

    if include_spatial and "spatial" not in result and dataset_index % 3 != 0:
        if dataset_index % 3 == 1:
            result["spatial"] = "United States"
        else:
            result["spatial"] = {
                "@type": "dct:Location",
                "geo": {
                    "type": "Point",
                    "coordinates": [-77.0365, 38.8977],
                },
            }

    if "license" not in result and dataset_index % 3 != 0:
        if dataset_index % 3 == 1:
            result["license"] = "https://creativecommons.org/publicdomain/zero/1.0/"

    if "contactPoint" not in result and dataset_index % 4 != 0:
        contact = {
            "@type": "vcard:Contact",
            "fn": f"Dataset support team {dataset_index + 1}",
            "hasEmail": f"mailto:data-team-{dataset_index + 1}@example.gov",
        }
        result["contactPoint"] = [contact] if dataset_index % 2 else contact

    if "issued" not in result and dataset_index % 3 != 0:
        result["issued"] = f"202{dataset_index % 5}-01-01"

    if "modified" not in result and dataset_index % 4 != 0:
        result["modified"] = f"202{2 + dataset_index % 5}-06-15"

    if "language" not in result and dataset_index % 5 != 0:
        result["language"] = ["en-US", "es"] if dataset_index % 2 else ["en-US"]

    if "rights" not in result and dataset_index % 4 == 1:
        result["rights"] = "Public domain or applicable open license."

    if "references" not in result and dataset_index % 6 == 1:
        result["references"] = [
            f"https://example.gov/references/dataset-{dataset_index + 1}"
        ]

    if "description" not in result:
        result["description"] = (
            f"Generated metadata coverage for dataset {dataset_index + 1}."
        )

    publisher = result.get("publisher")
    if isinstance(publisher, dict) and dataset_index % 12 == 1:
        publisher.setdefault("@type", "org:Organization")
        publisher["subOrganizationOf"] = [
            {
                "@type": "org:Organization",
                "name": f"Parent agency {dataset_index + 1}",
            }
        ]
    elif isinstance(publisher, dict) and dataset_index % 12 == 2:
        result["publisher"] = {
            "@type": "org:Organization",
            "prefLabel": publisher.get("name", "Test publisher"),
        }
    elif isinstance(publisher, dict) and dataset_index % 12 == 3:
        result["publisher"] = publisher.get("name", "Test publisher")

    distributions = result.get("distribution")
    if not isinstance(distributions, list):
        distributions = []
    else:
        distributions = copy.deepcopy(distributions)

    if dataset_index % 9 == 0:
        for resource_index in range(8):
            distributions.append(
                _supplemental_distribution(dataset_index, resource_index)
            )
    elif dataset_index % 7 != 0:
        distributions.append(_supplemental_distribution(dataset_index, 0))
    if "license" not in result and dataset_index % 3 == 2:
        first_resource = next(
            (resource for resource in distributions if isinstance(resource, dict)),
            None,
        )
        if first_resource is None:
            distributions.append(
                {
                    "title": "License metadata sample",
                    "license": "https://creativecommons.org/licenses/by/4.0/",
                }
            )
        else:
            first_resource.setdefault(
                "license", "https://creativecommons.org/licenses/by/4.0/"
            )
    result["distribution"] = distributions
    return result


def _stable_id(entity_type: str, *indexes: int) -> str:
    index_path = ":".join(map(str, indexes))
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"datagov-catalog-test-data:{FIXED_TEST_DATA_SEED}:{entity_type}:{index_path}",
        )
    )


def _add_topic_datasets(
    generated: FactoryFixtureData, existing_dataset_count: int
) -> None:
    source_by_organization = {
        source.organization_id: source for source in generated["harvest_sources"]
    }
    source_organizations = [
        (organization_id, source)
        for organization_id, source in source_by_organization.items()
    ]

    for profile_index, (slug_part, title, keywords, theme) in enumerate(TOPIC_PROFILES):
        for variation_index in range(2):
            dataset_index = existing_dataset_count + profile_index * 2 + variation_index
            organization_id, source = source_organizations[
                dataset_index % len(source_organizations)
            ]
            slug = f"generated-topic-{slug_part}-{variation_index + 1}"
            record_id = _stable_id(
                "topic-harvest-record", profile_index, variation_index
            )
            dataset_id = _stable_id("topic-dataset", profile_index, variation_index)
            dcat = {
                "@type": "dcat:Dataset",
                "title": f"{title} - Test Dataset {variation_index + 1}",
                "description": (
                    f"Sample {slug_part.replace('-', ' ')} data for testing "
                    "search, facets, and dataset detail metadata."
                ),
                "identifier": f"https://example.gov/datasets/{slug}",
                "keyword": keywords + [f"{slug_part} sample {variation_index + 1}"],
                "theme": [theme],
                "publisher": {
                    "@type": "org:Organization",
                    "name": f"{theme} Data Office",
                },
                "issued": f"202{variation_index + 1}-01-01",
                "modified": f"202{4 + variation_index}-06-15",
                "temporal": (
                    "2020-01-01/2024-12-31"
                    if variation_index == 0
                    else {
                        "startDate": "2020-01-01",
                        "endDate": "2024-12-31",
                    }
                ),
                "spatial": (
                    "United States"
                    if variation_index == 0
                    else {
                        "@type": "dct:Location",
                        "geo": {
                            "type": "Point",
                            "coordinates": [-77.0365, 38.8977],
                        },
                    }
                ),
                "language": ["en-US", "es"] if variation_index else ["en-US"],
                "license": (
                    "https://creativecommons.org/licenses/by/4.0/"
                    if variation_index == 0
                    else None
                ),
                "contactPoint": {
                    "@type": "vcard:Contact",
                    "fn": f"{theme} data support",
                    "hasEmail": f"mailto:{slug_part}@example.gov",
                },
                "distribution": [
                    {
                        "@type": "dcat:Distribution",
                        "title": (
                            f"{title} downloadable data"
                            if variation_index == 0
                            else f"{title} API endpoint"
                        ),
                        "format": "CSV" if variation_index == 0 else "API",
                        "mediaType": (
                            "text/csv" if variation_index == 0 else "application/json"
                        ),
                        (
                            "downloadURL" if variation_index == 0 else "accessURL"
                        ): f"https://example.gov/data/{slug}",
                    }
                ],
            }
            if dcat["license"] is None:
                dcat.pop("license")
                dcat["distribution"][0][
                    "license"
                ] = "https://creativecommons.org/licenses/by/4.0/"
            dataset = DatasetFactory.build(
                id=dataset_id,
                slug=slug,
                dcat=dcat,
                organization_id=organization_id,
                harvest_source_id=source.id,
                harvest_record_id=record_id,
                popularity=100 - dataset_index,
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
                type="dataset",
            )
            generated["datasets"].append(dataset)
            generated["harvest_records"].append(
                HarvestRecordFactory.build(
                    id=record_id,
                    identifier=slug,
                    harvest_job_id="1",
                    harvest_source_id=source.id,
                    source_raw=json.dumps(dcat),
                    source_transform=copy.deepcopy(dcat),
                )
            )


def generated_test_data(fixture_data: dict[str, Any]) -> FactoryFixtureData:
    """Build the full fixture dataset pool as FactoryBoy model instances."""
    previous_random_state = factory_random.get_random_state()
    factory_random.reseed_random(FIXED_TEST_DATA_SEED)
    try:
        datasets = []
        updated_metadata_by_record_id = {}
        for dataset_index, dataset_data in enumerate(fixture_data["dataset"]):
            dcat = _enrich_dataset_metadata(
                dataset_data["dcat"],
                dataset_index,
                include_spatial="translated_spatial" not in dataset_data,
            )
            dataset = DatasetFactory.build(**{**dataset_data, "dcat": dcat})
            datasets.append(dataset)
            updated_metadata_by_record_id[dataset.harvest_record_id] = dcat

        records = []
        for record_data in fixture_data["harvest_record"]:
            dcat = updated_metadata_by_record_id.get(record_data["id"])
            if dcat is None:
                records.append(HarvestRecordFactory.build(**record_data))
                continue
            source_raw = record_data.get("source_raw")
            if isinstance(source_raw, str):
                try:
                    raw_metadata = json.loads(source_raw)
                except json.JSONDecodeError:
                    raw_metadata = None
                if isinstance(raw_metadata, dict):
                    source_raw = json.dumps(dcat)
            records.append(
                HarvestRecordFactory.build(
                    **{
                        **record_data,
                        "source_raw": source_raw,
                        "source_transform": copy.deepcopy(dcat),
                    }
                )
            )

        generated: FactoryFixtureData = {
            "organizations": [
                OrganizationFactory.build(**data)
                for data in fixture_data["organization"]
            ],
            "harvest_sources": [
                HarvestSourceFactory.build(**data)
                for data in [
                    fixture_data["harvest_source"],
                    *fixture_data.get("extra_harvest_source", []),
                ]
            ],
            "harvest_records": records,
            "datasets": datasets,
        }
        _add_topic_datasets(generated, len(datasets))
        return generated
    finally:
        factory_random.set_random_state(previous_random_state)
