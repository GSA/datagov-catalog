import csv
import json
from datetime import datetime
from pathlib import Path

HARVEST_RECORD_ID = "e8b2ef79-8dbe-4d2e-9fe8-dc6766c0b5ab"
DATASET_ID = "e8b2ef79-8dbe-4d2e-9fe8-dc6766c0b5ab"
STOPWORD_RECORD_ID = "health-food-record"
STOPWORD_DATASET_ID = "health-food-dataset"
DCAT_3_0_RECORD_ID = "dcat-3-0-test-record"
DCAT_3_0_DATASET_ID = "dcat-3-0-test-dataset"
TEST_DIR = Path(__file__).parent
DEFAULT_LAST_HARVESTED_DATE = datetime(2023, 1, 1)


# helpers functions
def read_csv(file_path) -> list:
    output = []
    with open(file_path) as f:
        csv_reader = csv.reader(f)
        for row in csv_reader:
            output.append(row)
    return output


def _bbox_polygon(min_lon, min_lat, max_lon, max_lat):
    """Build a GeoJSON Polygon (for a dataset's translated_spatial) from a bbox."""
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def _bbox_wkt(min_lon, min_lat, max_lon, max_lat):
    """Build a WKT MULTIPOLYGON (for a Locations.the_geom) from a bbox."""
    return (
        "MULTIPOLYGON((("
        f"{min_lon} {min_lat},{max_lon} {min_lat},{max_lon} {max_lat},"
        f"{min_lon} {max_lat},{min_lon} {min_lat})))"
    )


# Demo organizations: one per non-Federal org type so the organization and
# organization-type filters have variety. Each gets its own harvest source.
# (id, name, slug, organization_type)
_DEMO_ORGS = [
    ("city-portland", "City of Portland", "city-of-portland", "City Government"),
    (
        "state-california",
        "State of California",
        "state-of-california",
        "State Government",
    ),
    ("county-cook", "Cook County", "cook-county", "County Government"),
    ("univ-michigan", "University of Michigan", "university-of-michigan", "University"),
    ("tribe-navajo", "Navajo Nation", "navajo-nation", "Tribal"),
    ("nonprofit-redcross", "American Red Cross", "american-red-cross", "Non-Profit"),
]

# Demo datasets. Each falls inside one of the demo locations so the "within"
# geography filter returns it. Fields:
# (slug, title, keywords, publisher, org_id, bbox-or-None)
_DEMO_DATASETS = [
    (
        "portland-bike-lanes",
        "Portland Bike Lane Network",
        ["transportation", "cycling"],
        "Portland Bureau of Transportation",
        "city-portland",
        (-122.75, 45.45, -122.55, 45.60),
    ),
    (
        "portland-park-trees",
        "Portland Park Tree Inventory",
        ["environment", "trees"],
        "Portland Parks and Recreation",
        "city-portland",
        (-122.70, 45.48, -122.60, 45.55),
    ),
    (
        "california-wildfire-perimeters",
        "California Wildfire Perimeters",
        ["wildfire", "environment", "emergency"],
        "California Department of Forestry and Fire Protection",
        "state-california",
        (-122.0, 37.0, -119.0, 39.0),
    ),
    (
        "california-water-quality",
        "California Surface Water Quality",
        ["water", "environment"],
        "California State Water Resources Control Board",
        "state-california",
        (-121.0, 36.5, -120.0, 38.0),
    ),
    (
        "cook-county-property-assessments",
        "Cook County Property Assessments",
        ["property", "taxes", "finance"],
        "Cook County Assessor's Office",
        "county-cook",
        (-87.95, 41.65, -87.55, 42.05),
    ),
    (
        "michigan-enrollment-stats",
        "University of Michigan Enrollment Statistics",
        ["education", "enrollment"],
        "University of Michigan Office of the Registrar",
        "univ-michigan",
        (-83.80, 42.22, -83.68, 42.32),
    ),
    (
        "michigan-research-grants",
        "University of Michigan Research Grants",
        ["research", "funding", "education"],
        "University of Michigan Office of Research",
        "univ-michigan",
        None,
    ),
    (
        "navajo-water-access",
        "Navajo Nation Water Access Points",
        ["water", "infrastructure"],
        "Navajo Nation Department of Water Resources",
        "tribe-navajo",
        (-110.5, 35.5, -109.0, 37.0),
    ),
    (
        "redcross-shelter-locations",
        "Red Cross Shelter Locations",
        ["emergency", "health", "shelter"],
        "American Red Cross",
        "nonprofit-redcross",
        None,
    ),
    (
        "redcross-blood-drives",
        "Red Cross Blood Drive Schedule",
        ["health", "blood", "volunteer"],
        "American Red Cross",
        "nonprofit-redcross",
        (-118.50, 33.90, -118.10, 34.20),
    ),
]

# Demo locations whose geometry covers the demo datasets above.
# (id, name, type, display_name, bbox, type_order)
_DEMO_LOCATIONS = [
    (101, "OR", "us_state", "Oregon", (-124.6, 41.9, -116.4, 46.3), 2),
    (102, "CA", "us_state", "California", (-124.5, 32.5, -114.1, 42.1), 2),
    (103, "MI", "us_state", "Michigan", (-90.5, 41.6, -82.1, 48.3), 2),
    (
        104,
        "Cook County",
        "us_county",
        "Cook County, Illinois",
        (-88.3, 41.4, -87.5, 42.2),
        3,
    ),
    (
        105,
        "Portland",
        "us_place",
        "Portland, Oregon",
        (-122.9, 45.4, -122.4, 45.7),
        4,
    ),
    (
        106,
        "Los Angeles",
        "us_place",
        "Los Angeles, California",
        (-118.7, 33.7, -118.1, 34.3),
        4,
    ),
]


def _add_filter_demo_data(fixture_dict):
    """Append demo orgs, harvest sources, datasets, and locations in place."""
    job_id = fixture_dict["harvest_job"]["id"]
    fixture_dict.setdefault("extra_harvest_source", [])

    for org_id, name, slug, org_type in _DEMO_ORGS:
        fixture_dict["organization"].append(
            dict(id=org_id, name=name, slug=slug, organization_type=org_type)
        )
        fixture_dict["extra_harvest_source"].append(
            dict(
                id=f"src-{org_id}",
                name=f"{name} source",
                organization_id=org_id,
                url=f"https://example.com/sources/{slug}",
                frequency="manual",
                schema_type="dcatus1.1: non-federal",
                source_type="document",
                notification_frequency="always",
            )
        )

    for index, (slug, title, keywords, publisher, org_id, bbox) in enumerate(
        _DEMO_DATASETS
    ):
        record_id = f"demo-record-{index}"
        dcat = {
            "title": title,
            "description": f"Demo dataset for filter testing: {title}.",
            "keyword": keywords,
            "identifier": slug,
            "modified": "2025-01-15",
            "publisher": {"name": publisher},
            "distribution": [
                {
                    "title": f"{title} (CSV)",
                    "format": "CSV",
                    "downloadURL": f"https://example.com/{slug}.csv",
                }
            ],
        }
        fixture_dict["harvest_record"].append(
            dict(
                id=record_id,
                harvest_source_id=f"src-{org_id}",
                harvest_job_id=job_id,
                identifier=slug,
                source_raw=json.dumps(dcat),
                source_transform=dcat,
            )
        )
        fixture_dict["dataset"].append(
            dict(
                id=f"demo-dataset-{index}",
                slug=slug,
                dcat=dcat,
                harvest_record_id=record_id,
                harvest_source_id=f"src-{org_id}",
                organization_id=org_id,
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
                popularity=50 + index,
                translated_spatial=_bbox_polygon(*bbox) if bbox else None,
            )
        )

    for loc_id, loc_name, loc_type, display_name, bbox, type_order in _DEMO_LOCATIONS:
        fixture_dict["locations"].append(
            {
                "id": loc_id,
                "name": loc_name,
                "type": loc_type,
                "display_name": display_name,
                "the_geom": _bbox_wkt(*bbox),
                "type_order": type_order,
            }
        )


def fixture_data(*, include_filter_demos: bool = False):
    fixture_dict = {
        "organization": [
            dict(
                id="1",
                name="test org",
                slug="test-org",
                organization_type="Federal Government",
                aliases=["aliasonly"],
            ),
            dict(
                id="2",
                name="test org filtered",
                slug="test-org-filtered",
                organization_type="Federal Government",
            ),
        ],
        "harvest_source": dict(
            id="1",
            name="test-source",
            organization_id="1",
            url="not-a-url",
            frequency="manual",
            schema_type="dcatus1.1: non-federal",
            source_type="document",
            notification_frequency="always",
        ),
        "harvest_job": dict(id="1", harvest_source_id="1", status="complete"),
        "harvest_record": [
            dict(
                id=HARVEST_RECORD_ID,
                harvest_source_id="1",
                harvest_job_id="1",
                identifier="identifier",
                source_raw='{"title": "test dataset"}',
                source_transform={
                    "title": "test dataset",
                    "extras": {"foo": "bar"},
                },
            ),
            dict(
                id=STOPWORD_RECORD_ID,
                harvest_source_id="1",
                harvest_job_id="1",
                identifier="health-food-dataset",
                source_raw='{"title": "Health Food Access Statistics"}',
                source_transform={
                    "title": "Health Food Access Statistics",
                },
            ),
            dict(
                id="parent_harvest_record",
                harvest_source_id="1",
                harvest_job_id="1",
                identifier="https://subdomain.domain/parent/example.shp.iso.xml",
                source_raw='{"title": "Parent Harvest Record": "isPartOf": "https://subdomain.domain/parent/example.shp.iso.xml"}',
                source_transform={
                    "title": "Parent Harvest Record",
                    "isPartOf": "https://subdomain.domain/parent/example.shp.iso.xml",
                },
            ),
            dict(
                id="child_harvest_record",
                harvest_source_id="1",
                harvest_job_id="1",
                identifier="https://subdomain.domain/child/example.shp.iso.xml",
                source_raw='{"title": "Child Harvest Record": "isPartOf": "https://subdomain.domain/parent/example.shp.iso.xml"}',
                source_transform={
                    "title": "Child Harvest Record",
                    "isPartOf": "https://subdomain.domain/parent/example.shp.iso.xml",
                },
            ),
            dict(
                id="child_no_parent_harvest_record",
                harvest_source_id="1",
                harvest_job_id="1",
                identifier="https://subdomain.domain/child_no_parent/example.shp.iso.xml",
                source_raw='{"title": "Child With No Parent Harvest Record": "isPartOf": "https://subdomain.domain/missing_parent/example.shp.iso.xml"}',
                source_transform={
                    "title": "Child Harvest Record",
                    "isPartOf": "https://subdomain.domain/missing_parent/example.shp.iso.xml",
                },
            ),
            dict(
                id=DCAT_3_0_RECORD_ID,
                harvest_source_id="1",
                harvest_job_id="1",
                identifier="dcat-3-0-test-identifier",
                source_raw='{"title": "DCAT-US 3.0 Test Dataset"}',
                source_transform={
                    "title": "DCAT-US 3.0 Test Dataset",
                },
            ),
        ],
        "dataset": [
            dict(
                id=DATASET_ID,
                slug="test",
                dcat={
                    "title": "test",
                    "description": "this is the test description",
                    "keyword": ["health", "education", "Health"],
                    "identifier": "test identifier",
                    "modified": "2026-03-04",
                    "publisher": {"name": "test publisher"},
                    "contactPoint": {
                        "fn": "Test Contact",
                        "hasEmail": "mailto:test.contact@example.gov",
                    },
                    "distribution": [
                        {
                            "title": "Test CSV",
                            "description": "Sample CSV resource",
                            "format": "CSV",
                            "downloadURL": "https://example.com/test.csv",
                            "mediaType": "text/csv",
                        }
                    ],
                },
                harvest_record_id=HARVEST_RECORD_ID,
                harvest_source_id="1",
                organization_id="1",
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
                translated_spatial={
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-80.542601, 36.666691],
                            [-80.542601, 42.987042],
                            [-74.580735, 42.987042],
                            [-74.580735, 36.666691],
                            [-80.542601, 36.666691],
                        ]
                    ],
                },
            ),
            dict(
                id="test-dataset-2",
                slug="test-health-data",
                dcat={
                    "title": "Health and Medical Research Data",
                    "description": "Comprehensive health statistics and medical research findings",
                    "keyword": ["health", "medical", "research"],
                    "publisher": {"name": "Department of Health Research"},
                    "contactPoint": {
                        "fn": "Dr. Jane Smith",
                        "hasEmail": "mailto:jane.smith@example.gov",
                    },
                    "distribution": [
                        {
                            "title": "Health Statistics",
                            "format": "JSON",
                            "downloadURL": "https://example.com/health.json",
                        }
                    ],
                },
                harvest_record_id=HARVEST_RECORD_ID,
                harvest_source_id="1",
                organization_id="1",
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
                popularity=100,
            ),
            dict(
                id="test-dataset-3",
                slug="test-climate-environment",
                dcat={
                    "title": "Climate Change Environmental Data",
                    "description": "Environmental monitoring and climate science datasets",
                    "keyword": ["environment", "science", "climate", "Environment"],
                    "spatial": "-122.4194,37.7749,-122.4094,37.7849",
                    "identifier": "test climate environment",
                    "modified": "2026-03-04",
                    "publisher": {"name": "test publisher"},
                    "contactPoint": {
                        "fn": "Climate Data Office",
                        "hasEmail": "mailto:climate@example.gov",
                    },
                    "distribution": [
                        {
                            "title": "Climate Measurements",
                            "format": "CSV",
                            "downloadURL": "https://example.com/climate.csv",
                        }
                    ],
                },
                harvest_record_id=HARVEST_RECORD_ID,
                harvest_source_id="1",
                organization_id="1",
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
                popularity=250,
            ),
            dict(
                id="test-dataset-4",
                slug="test-education-schools",
                dcat={
                    "title": "Education and School Performance Data",
                    "description": "School statistics and educational outcomes",
                    "keyword": [],
                    "publisher": {"name": "Department of Education"},
                    "contactPoint": {
                        "fn": "Not provided - Contact data.gov",
                        "hasEmail": "mailto:datagovsupport@gsa.gov",
                    },
                    "distribution": [
                        {
                            "title": "School Data",
                            "format": "XLSX",
                            "downloadURL": "https://example.com/schools.xlsx",
                        }
                    ],
                },
                harvest_record_id=HARVEST_RECORD_ID,
                harvest_source_id="1",
                organization_id="1",
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
                popularity=180,
            ),
            dict(
                id="test-dataset-5",
                slug="test-technology-data",
                dcat={
                    "title": "Technology and Data Science Resources",
                    "description": "Technology trends and data science methodologies",
                    "keyword": ["technology", "data", "science"],
                    "publisher": {"name": "test publisher"},
                    "contactPoint": {
                        "fn": "Not provided - Contact data.gov",
                        "hasEmail": "mailto:datagovsupport@gsa.gov",
                    },
                    "distribution": [
                        {
                            "title": "Tech Trends",
                            "format": "PDF",
                            "downloadURL": "https://example.com/tech.pdf",
                        }
                    ],
                },
                harvest_record_id=HARVEST_RECORD_ID,
                harvest_source_id="1",
                organization_id="1",
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
                popularity=150,
            ),
            dict(
                id=STOPWORD_DATASET_ID,
                slug="health-food-access",
                dcat={
                    "title": "Health Food Access Statistics",
                    "description": "National statistics on access to health food resources",
                    "keyword": ["health", "food"],
                    "publisher": {"name": "test publisher"},
                    "contactPoint": {
                        "fn": "Not provided - Contact data.gov",
                        "hasEmail": "mailto:datagovsupport@gsa.gov",
                    },
                    "distribution": [
                        {
                            "title": "Health Food Data",
                            "format": "CSV",
                            "downloadURL": "https://example.com/health-food.csv",
                        }
                    ],
                },
                harvest_record_id=STOPWORD_RECORD_ID,
                harvest_source_id="1",
                organization_id="1",
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
                popularity=125,
            ),
            dict(
                id="parent1234567",
                slug="parent-harvest-record",
                dcat={
                    "title": "Parent Harvest Record",
                    "description": "National statistics on access to health food resources",
                    "keyword": ["health", "food"]
                    * 25,  # the tag/keyword section is collapsible in dataset_detail.html (max 8 tags)
                    "modified": "2026-03-04",
                    "publisher": {"name": "test parent publisher"},
                    "contactPoint": {
                        "fn": "Not provided - Contact data.gov",
                        "hasEmail": "mailto:datagovsupport@gsa.gov",
                    },
                    "distribution": [
                        {
                            "title": "Health Food Data",
                            "format": "CSV",
                            "downloadURL": "https://example.com/health-food.csv",
                        }
                    ],
                    "identifier": "https://subdomain.domain/parent/example.shp.iso.xml",
                    "isPartOf": "https://subdomain.domain/parent/example.shp.iso.xml",
                },
                harvest_record_id="parent_harvest_record",
                harvest_source_id="1",
                organization_id="1",
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
                popularity=125,
                translated_spatial={
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-125.0, 24.0],
                            [-67.0, 24.0],
                            [-67.0, 50.0],
                            [-125.0, 50.0],
                            [-125.0, 24.0],
                        ]
                    ],
                },
            ),
            dict(
                id="earth-keyword-dataset",
                slug="earth-keyword-dataset",
                dcat={
                    "title": "Earth Observation Dataset",
                    "description": "Dataset tagged with the keyword earth",
                    "keyword": ["earth"],
                    "publisher": {"name": "test publisher"},
                    "contactPoint": {
                        "fn": "Not provided - Contact data.gov",
                        "hasEmail": "mailto:datagovsupport@gsa.gov",
                    },
                },
                harvest_record_id=HARVEST_RECORD_ID,
                harvest_source_id="1",
                organization_id="1",
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
            ),
            dict(
                id="earth-science-keyword-dataset",
                slug="earth-science-keyword-dataset",
                dcat={
                    "title": "Earth Science Dataset",
                    "description": "Dataset tagged with the keyword earth science",
                    "keyword": ["earth science"],
                    "publisher": {"name": "test publisher"},
                    "contactPoint": {
                        "fn": "Not provided - Contact data.gov",
                        "hasEmail": "mailto:datagovsupport@gsa.gov",
                    },
                },
                harvest_record_id=HARVEST_RECORD_ID,
                harvest_source_id="1",
                organization_id="1",
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
            ),
            dict(
                id="earth-science-trees-keyword-dataset",
                slug="earth-science-trees-keyword-dataset",
                dcat={
                    "title": "Earth Science Trees Dataset",
                    "description": "Dataset tagged with the keyword earth science > trees",
                    "keyword": ["earth science > trees"],
                    "publisher": {"name": "test publisher"},
                    "contactPoint": {
                        "fn": "Not provided - Contact data.gov",
                        "hasEmail": "mailto:datagovsupport@gsa.gov",
                    },
                },
                harvest_record_id=HARVEST_RECORD_ID,
                harvest_source_id="1",
                organization_id="1",
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
            ),
            dict(
                id="child1234567",
                slug="child-harvest-record",
                dcat={
                    "title": "Child Harvest Record",
                    "description": "National statistics on access to health food resources",
                    "keyword": ["health", "food"],
                    "modified": "2026-03-04",
                    "publisher": {"name": "test child publisher"},
                    "contactPoint": {
                        "fn": "Not provided - Contact data.gov",
                        "hasEmail": "mailto:datagovsupport@gsa.gov",
                    },
                    "distribution": [
                        {
                            "title": "Health Food Data",
                            "format": "CSV",
                            "downloadURL": "https://example.com/health-food.csv",
                        }
                    ],
                    "identifier": "https://subdomain.domain/child/example.shp.iso.xml",
                    "isPartOf": "https://subdomain.domain/parent/example.shp.iso.xml",
                },
                harvest_record_id="child_harvest_record",
                harvest_source_id="1",
                organization_id="1",
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
                popularity=125,
                translated_spatial={
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-125.0, 24.0],
                            [-67.0, 24.0],
                            [-67.0, 50.0],
                            [-125.0, 50.0],
                            [-125.0, 24.0],
                        ]
                    ],
                },
            ),
            dict(
                id=DCAT_3_0_DATASET_ID,
                slug="test-dcat-3-0",
                dcat={
                    "@type": "dcat:Dataset",
                    "identifier": "dcat-3-0-test-identifier",
                    "title": "DCAT-US 3.0 Test Dataset",
                    "description": "This is a sample dataset using DCAT-US 3.0 schema for testing the normalization layer. It includes all the major changes from version 1.1 to 3.0.",
                    "keyword": [
                        "sample",
                        "testing",
                        "dcat-us-3.0",
                        "climate",
                        "environment",
                    ],
                    "modified": "2024-10-01",
                    "accrualPeriodicity": "annually",
                    "issued": "2020-01-15T00:00:00Z",
                    "publisher": {
                        "@type": "org:Organization",
                        "name": "Sample Federal Agency",
                        "subOrganizationOf": [
                            {
                                "@type": "org:Organization",
                                "name": "Department of Sample Services",
                            }
                        ],
                    },
                    "contactPoint": {
                        "@type": "vcard:Contact",
                        "fn": "Jane Doe",
                        "hasEmail": "mailto:jane.doe@example.gov",
                    },
                    "accessLevel": "public",
                    "accessRights": "public",
                    "license": "https://creativecommons.org/publicdomain/zero/1.0/",
                    "rights": [
                        "This data is in the public domain and available for unrestricted use."
                    ],
                    "temporal": [
                        {
                            "@type": "PeriodOfTime",
                            "startDate": "2000-01-15",
                            "endDate": "2023-12-31",
                        }
                    ],
                    "spatial": [
                        {
                            "@type": "Location",
                            "prefLabel": "United States",
                        }
                    ],
                    "language": ["en"],
                    "conformsTo": [
                        {
                            "@type": "Standard",
                            "identifier": "https://www.iso.org/standard/53798.html",
                            "title": "ISO 19115",
                        }
                    ],
                    "landingPage": {
                        "@type": "Document",
                        "title": "Sample Dataset Landing Page",
                        "accessURL": "https://example.gov/datasets/sample-dcat-3-0",
                    },
                    "describedBy": {
                        "@type": "Distribution",
                        "accessURL": "https://example.gov/schemas/sample-schema.json",
                        "mediaType": "application/schema+json",
                    },
                    "distribution": [
                        {
                            "@type": "dcat:Distribution",
                            "title": "Sample CSV Data File",
                            "description": "Complete dataset in CSV format",
                            "downloadURL": "https://example.gov/data/sample-data.csv",
                            "mediaType": "text/csv",
                            "format": "CSV",
                            "license": "https://creativecommons.org/publicdomain/zero/1.0/",
                        },
                        {
                            "@type": "dcat:Distribution",
                            "title": "Sample JSON Data File",
                            "description": "Complete dataset in JSON format",
                            "downloadURL": "https://example.gov/data/sample-data.json",
                            "accessURL": "https://example.gov/data/sample-data.json",
                            "mediaType": "application/json",
                            "format": "JSON",
                            "license": "https://creativecommons.org/publicdomain/zero/1.0/",
                        },
                        {
                            "@type": "dcat:Distribution",
                            "title": "Sample API Endpoint",
                            "description": "REST API access to the dataset",
                            "accessURL": "https://api.example.gov/v1/sample-data",
                            "mediaType": "application/json",
                            "format": "API",
                        },
                    ],
                    "theme": ["Climate", "Environment"],
                    "isPartOf": "sample-collection-2024",
                },
                harvest_record_id=DCAT_3_0_RECORD_ID,
                harvest_source_id="1",
                organization_id="1",
                last_harvested_date=DEFAULT_LAST_HARVESTED_DATE,
                popularity=150,
                translated_spatial={
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-125.0, 24.0],
                            [-67.0, 24.0],
                            [-67.0, 50.0],
                            [-125.0, 50.0],
                            [-125.0, 24.0],
                        ]
                    ],
                },
            ),
        ],
        "locations": [
            {
                "id": 1,
                "name": "20006",
                "type": "us_postalcode",
                "display_name": "Washington, DC (20006)",
                # geoalchemy needs WKT format geometries
                "the_geom": "MULTIPOLYGON(((-77.0467 38.8878,-77.0467 38.9027,-77.0329 38.9027,-77.0329 38.8878,-77.0467 38.8878)))",
                "type_order": 4,
            },
        ],
    }

    if include_filter_demos:
        _add_filter_demo_data(fixture_dict)

    # add additional dataset records
    datasets = read_csv(TEST_DIR / "data" / "americorps_datasets.csv")
    fields = datasets[0]
    org_id = fixture_dict["organization"][0]["id"]
    harvest_source_id = fixture_dict["harvest_source"]["id"]
    harvest_job_id = fixture_dict["harvest_job"]["id"]

    for row in datasets[1:]:
        slug = row[0]
        dcat = json.loads(row[1])
        harvest_record_id = row[4]
        popularity = int(row[5])

        fixture_dict["harvest_record"].append(
            dict(
                id=harvest_record_id,
                harvest_source_id=harvest_source_id,
                harvest_job_id=harvest_job_id,
                identifier=slug,
                source_raw=json.dumps(dcat),
                source_transform=dcat,
            )
        )

        row[1] = dcat
        row[2] = org_id
        row[3] = harvest_source_id
        row[5] = popularity
        last_harvested_raw = row[6].strip() if len(row) > 6 and row[6] else ""
        if last_harvested_raw:
            try:
                last_harvested_date = datetime.fromisoformat(last_harvested_raw)
            except ValueError:
                last_harvested_date = DEFAULT_LAST_HARVESTED_DATE
        else:
            last_harvested_date = DEFAULT_LAST_HARVESTED_DATE
        row[6] = last_harvested_date
        fixture_dict["dataset"].append(dict(zip(fields, row)))
    return fixture_dict
