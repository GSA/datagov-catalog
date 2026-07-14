from copy import deepcopy
from typing import Any


def normalize_rights(rights: Any) -> str | None:

    if not rights:
        return None

    if isinstance(rights, str):
        return rights

    # get the rights as the first element if this comes as a list
    if isinstance(rights, list):
        return rights[0]

    return None


def normalize_landing_page(landing_page: Any) -> str | None:

    if not landing_page:
        return None

    if isinstance(landing_page, str):
        return landing_page

    if isinstance(landing_page, dict):
        return landing_page.get("accessURL")

    return None


def normalize_described_by(described_by: Any) -> str | None:

    if not described_by:
        return None

    if isinstance(described_by, str):
        return described_by

    if isinstance(described_by, dict):
        return described_by.get("accessURL")

    return None


def normalize_temporal(temporal: Any) -> str | None:

    if not temporal:
        return None

    if isinstance(temporal, str):
        return temporal

    if isinstance(temporal, list):
        # get the period of temporal as the first element if this comes as a list
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

    if not modified:
        return None

    if isinstance(modified, str):
        # Remove repeating interval patterns like R/P1Y
        if modified.startswith("R/"):
            return None
        return modified

    return None


def normalize_issued(issued: Any) -> str | None:

    if not issued:
        return None

    if isinstance(issued, str):
        return issued

    return None


def normalize_access_rights(access_rights: Any, access_level: Any = None) -> str | None:

    if access_level:
        return access_level

    if access_rights:
        return access_rights

    return None


def normalize_language(language: Any) -> list[str] | None:

    # Mapping of ISO 639-1 codes to RFC 5646 tags commonly used in federal data
    LANGUAGE_MAPPING = {
        "en": "en-US",
        "es": "es-US",
        "fr": "fr-FR",
        "de": "de-DE",
        "zh": "zh-CN",
        "ja": "ja-JP",
        "ko": "ko-KR",
        "ar": "ar-SA",
        "pt": "pt-BR",
        "ru": "ru-RU",
        "it": "it-IT",
        "nl": "nl-NL",
        "pl": "pl-PL",
        "tr": "tr-TR",
        "vi": "vi-VN",
        "th": "th-TH",
        "hi": "hi-IN",
    }

    if not language:
        return None

    if isinstance(language, str):
        if "-" in language:
            return [language]
        return [LANGUAGE_MAPPING.get(language, language)]

    if isinstance(language, list):
        normalized = []
        for lang in language:
            if isinstance(lang, str):
                if "-" in lang:
                    normalized.append(lang)
                else:
                    normalized.append(LANGUAGE_MAPPING.get(lang, lang))
        return normalized if normalized else None

    return None


def normalize_accrual_periodicity(accrual_periodicity: Any) -> str | None:

    if not accrual_periodicity:
        return None

    if isinstance(accrual_periodicity, str):
        return accrual_periodicity

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


def normalize_dcat_for_display(dcat: dict) -> dict:

    normalized = deepcopy(dcat)

    if "rights" in normalized:
        result = normalize_rights(normalized["rights"])
        if result:
            normalized["rights"] = result

    if "landingPage" in normalized:
        result = normalize_landing_page(normalized["landingPage"])
        if result:
            normalized["landingPage"] = result

    if "describedBy" in normalized:
        result = normalize_described_by(normalized["describedBy"])
        if result:
            normalized["describedBy"] = result

    if "temporal" in normalized:
        result = normalize_temporal(normalized["temporal"])
        if result:
            normalized["temporal"] = result

    if "spatial" in normalized:
        result = normalize_spatial(normalized["spatial"])
        if result:
            normalized["spatial"] = result

    if "conformsTo" in normalized:
        result = normalize_conforms_to(normalized["conformsTo"])
        if result:
            normalized["conformsTo"] = result

    if "modified" in normalized:
        result = normalize_modified(normalized["modified"])
        if result:
            normalized["modified"] = result

    if "issued" in normalized:
        result = normalize_issued(normalized["issued"])
        if result:
            normalized["issued"] = result

    if "accessRights" in normalized or "accessLevel" in normalized:
        result = normalize_access_rights(
            normalized.get("accessRights"), normalized.get("accessLevel")
        )
        if result:
            normalized["accessLevel"] = result

    if "language" in normalized:
        result = normalize_language(normalized["language"])
        if result:
            normalized["language"] = result

    if "accrualPeriodicity" in normalized:
        result = normalize_accrual_periodicity(normalized["accrualPeriodicity"])
        if result:
            normalized["accrualPeriodicity"] = result

    if "publisher" in normalized:
        normalized["publisher"] = normalize_publisher_sub_org(normalized["publisher"])

    # Move license from distribution to dataset level
    normalized = normalize_distribution_license(normalized)

    return normalized
