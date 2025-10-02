"""Utility helpers shared across the catalog app."""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar
from uuid import UUID

from flask import Response, jsonify

F = TypeVar("F", bound=Callable[..., Response])


def is_valid_uuid4(uuid_string: str) -> bool:
    """Return True if the string is a valid UUID4, otherwise False."""

    try:
        return str(UUID(uuid_string, version=4)) == uuid_string
    except ValueError:
        return False
    except AttributeError:
        return False


def json_not_found() -> Response:
    return jsonify({"error": "Not Found"}), 404


def valid_id_required(func: F) -> F:
    """Decorator that ensures all route params are valid UUID4 values."""

    @wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore[misc]
        for arg in args:
            if not is_valid_uuid4(arg):
                return json_not_found()
        for value in kwargs.values():
            if not is_valid_uuid4(value):
                return json_not_found()
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
