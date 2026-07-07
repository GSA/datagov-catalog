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


def normalize_spatial(spatial: Any) -> str | None:
    """
    Convert DCAT 3.0 spatial (Location object array) back to 1.1 format (string or bbox).

    v3.0: [{"@type": "Location", "prefLabel": "United States"}]
    v1.1: "United States"
    """
    if not spatial:
        return None

    if isinstance(spatial, str):
        return spatial

    if isinstance(spatial, list) and len(spatial) > 0:
        location = spatial[0]
        if isinstance(location, dict):
            if "prefLabel" in location:
                return location["prefLabel"]
            if "bbox" in location:
                return location["bbox"]
            if "geometry" in location:
                return location["geometry"]

    return None


def normalize_conforms_to(conforms_to: Any) -> str | list[str] | None:
    """
    Convert DCAT 3.0 conformsTo (Standard object array) back to 1.1 format (URI string or array).

    v3.0: [{"@type": "Standard", "identifier": "https://www.iso.org/standard/53798.html"}]
    v1.1: "https://www.iso.org/standard/53798.html"
    """
    if not conforms_to:
        return None

    if isinstance(conforms_to, str):
        return conforms_to

    if isinstance(conforms_to, list):
        identifiers = []
        for item in conforms_to:
            if isinstance(item, dict) and "identifier" in item:
                identifiers.append(item["identifier"])
            elif isinstance(item, str):
                identifiers.append(item)

        if len(identifiers) == 1:
            return identifiers[0]
        elif len(identifiers) > 1:
            return identifiers

    return None


def normalize_modified(modified: Any) -> str | None:
    """
    Ensure DCAT 3.0 modified is in ISO date format (not repeating intervals).

    v3.0: "2024-10-01" or "R/P1Y"
    v1.1: "2024-10-01"
    """
    if not modified:
        return None

    if isinstance(modified, str):
        # Remove repeating interval patterns like R/P1Y
        if modified.startswith("R/"):
            return None
        return modified

    return None
