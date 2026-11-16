from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import url_for


def criteria_url_for(
    endpoint: str, params: Mapping[str, Any] | None = None, **extra
) -> str:
    values: dict[str, Any] = {}
    for source in (params or {}, extra):
        for key, value in source.items():
            if value is None or value == []:
                continue
            values[key] = value
    # Werkzeug follows HTML form encoding and represents spaces as ``+``.
    # Use the RFC 3986 representation instead so generated search URLs are
    # handled consistently by infrastructure in front of the application.
    # issue: https://github.com/GSA/data.gov/issues/6465
    return url_for(endpoint, **values).replace("+", "%20")
