from typing import Any


def normalize_access_rights(access_rights: Any, access_level: Any = None) -> str | None:

    if access_level:
        return access_level

    if access_rights:
        return access_rights

    return None


def normalize_publisher_sub_org(publisher: dict) -> dict:

    if not isinstance(publisher, dict):
        return publisher

    publisher_copy = publisher.copy()
    sub_org = publisher_copy.get("subOrganizationOf")

    if isinstance(sub_org, list) and len(sub_org) > 0:
        publisher_copy["subOrganizationOf"] = sub_org[0]
        # recursively normalize nested subOrganizationOf
        if isinstance(publisher_copy["subOrganizationOf"], dict):
            publisher_copy["subOrganizationOf"] = normalize_publisher_sub_org(
                publisher_copy["subOrganizationOf"]
            )

    return publisher_copy


def normalize_distribution_license(dcat: dict) -> dict:

    dcat_copy = dcat.copy()
    distributions = dcat_copy.get("distribution")

    if not distributions or not isinstance(distributions, list):
        return dcat_copy

    # If dataset doesn't have license, get it from first distribution
    if not dcat_copy.get("license") and len(distributions) > 0:
        first_dist = distributions[0]
        if isinstance(first_dist, dict) and "license" in first_dist:
            dcat_copy["license"] = first_dist["license"]

    return dcat_copy
