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
