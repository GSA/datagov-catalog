import csv
import json
from pathlib import Path

from sqlalchemy import func

HARVEST_RECORD_ID = "e8b2ef79-8dbe-4d2e-9fe8-dc6766c0b5ab"
DATASET_ID = "e8b2ef79-8dbe-4d2e-9fe8-dc6766c0b5ab"
TEST_DIR = Path(__file__).parent


# helpers functions
def read_csv(file_path) -> list:
    output = []
    with open(file_path) as f:
        csv_reader = csv.reader(f)
        for row in csv_reader:
            output.append(row)
    return output


def fixture_data():
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
        "harvest_record": dict(
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
        "dataset": [
            dict(
                id=DATASET_ID,
                slug="test",
                dcat={
                    "title": "test",
                    "description": "this is the test description",
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
                search_vector=func.to_tsvector("english", "test description"),
            ),
        ],
    }

    # add additional dataset records
    datasets = read_csv(TEST_DIR / "data" / "americorps_datasets.csv")
    fields = datasets[0]

    for row in datasets[1:]:
        row[-2] = func.to_tsvector("english", row[1])  # search_vector
        row[1] = json.loads(row[1])  # dcat
        row[5] = int(row[5])  # popularity
        fixture_dict["dataset"].append(dict(zip(fields, row)))
    return fixture_dict
