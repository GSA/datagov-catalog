"""Utility helpers shared across the catalog app."""

from __future__ import annotations

import base64
import json
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


def build_dataset_dict(dataset_dict: dict) -> dict:
    """Convert an OpenSearch result dict into a dictionary."""
    # remove the search_vector from the dataset dict
    dataset_dict = {k: v for k, v in dataset_dict.items() if k != "search_vector"}
    return dataset_dict


def dict_from_hint(hint_string):
    """Compute a dict of args from our hint string.

    The hint string is a base64 encoded JSON string. An argument of None
    returns an empty dict and if there is an error decoding the hint,
    it also returns an empty dict.
    """
    if hint_string is None:
        return dict()

    try:
        return json.loads(base64.urlsafe_b64decode(hint_string).decode("utf-8"))
    except ValueError:
        return dict()


def hint_from_dict(args_dict):
    """Compute our URL hint from a dict of args.

    The hint string is a base64 encoded JSON string.
    """
    return base64.urlsafe_b64encode(
        json.dumps(args_dict, separators=(",", ":")).encode("utf-8")
    ).decode("utf-8")
