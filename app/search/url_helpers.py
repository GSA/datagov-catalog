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
    return url_for(endpoint, **values)
