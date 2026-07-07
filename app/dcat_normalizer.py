from typing import Any


def normalize_rights(rights: Any) -> str | None:
    """
    Convert DCAT 3.0 rights (array) back to 1.1 format (string).

    v3.0: ["This data is in the public domain."]
    v1.1: "This data is in the public domain."
    """
    if not rights:
        return None

    if isinstance(rights, str):
        return rights

    if isinstance(rights, list) and len(rights) > 0:
        return rights[0]

    return None


def normalize_landing_page(landing_page: Any) -> str | None:
    """
    Convert DCAT 3.0 landingPage (Document object) back to 1.1 format (URL string).

    v3.0: {"@type": "Document", "title": "Air Quality Data", "accessURL": "https://agency.gov/air-quality"}
    v1.1: "https://agency.gov/air-quality"
    """
    if not landing_page:
        return None

    if isinstance(landing_page, str):
        return landing_page

    if isinstance(landing_page, dict):
        return landing_page.get("accessURL")

    return None


def normalize_described_by(described_by: Any) -> str | None:
    """
    Convert DCAT 3.0 describedBy (Distribution object) back to 1.1 format (URL string).

    v3.0: {"accessURL": "https://agency.gov/schema.json", "mediaType": "application/schema+json"}
    v1.1: "https://agency.gov/schema.json"
    """
    if not described_by:
        return None

    if isinstance(described_by, str):
        return described_by

    if isinstance(described_by, dict):
        return described_by.get("accessURL")

    return None


def normalize_temporal(temporal: Any) -> str | None:
    """
    Convert DCAT 3.0 temporal (PeriodOfTime array) back to 1.1 format (ISO 8601 interval string).

    v3.0: [{"@type": "PeriodOfTime", "startDate": "2000-01-15", "endDate": "2010-01-15"}]
    v1.1: "2000-01-15T00:00:00Z/2010-01-15T00:00:00Z"
    """
    if not temporal:
        return None

    if isinstance(temporal, str):
        return temporal

    if isinstance(temporal, list) and len(temporal) > 0:
        period = temporal[0]
        if isinstance(period, dict):
            start = period.get("startDate")
            end = period.get("endDate")
            if start and end:
                start_normalized = start if "T" in start else f"{start}T00:00:00Z"
                end_normalized = end if "T" in end else f"{end}T00:00:00Z"
                return f"{start_normalized}/{end_normalized}"
            elif start:
                return start

    return None
