import copy
import json
import uuid

from app.models import Dataset, HarvestRecord


def unique_harvest_record_id(dataset_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"datagov-catalog-test:{dataset_id}"))


def add_dataset_with_harvest_record(interface, dataset_data):
    dataset_data = copy.deepcopy(dataset_data)
    dataset_data["harvest_record_id"] = unique_harvest_record_id(dataset_data["id"])

    dcat = dataset_data.get("dcat", {})
    interface.db.add(
        HarvestRecord(
            id=dataset_data["harvest_record_id"],
            harvest_source_id=dataset_data["harvest_source_id"],
            harvest_job_id="1",
            identifier=dcat.get("identifier", dataset_data["slug"]),
            source_raw=json.dumps(dcat, default=str),
            source_transform=dcat,
        )
    )
    # Flush the parent before adding the child. app/models.py declares no
    # ForeignKey, so SQLAlchemy can't dependency-sort these INSERTs; against
    # catalog's own FK-less schema the order doesn't matter, but harvester's real
    # schema enforces dataset.harvest_record_id -> harvest_record.id, and the
    # contract test (GSA/data.gov#6210) runs these fixtures against that schema.
    interface.db.flush()

    dataset = Dataset(**dataset_data)
    interface.db.add(dataset)
    return dataset
