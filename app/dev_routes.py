"""Development-only routes (not used in production behind nginx)."""

from __future__ import annotations

import logging

import requests
from flask import Response

logger = logging.getLogger(__name__)


def register_dev_routes(app) -> None:
    """Register routes only needed for local development."""
    if not app.config.get("IS_LOCAL"):
        return
