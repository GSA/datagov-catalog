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

    # Map tiles are served from a same-origin /maptiles path so the CSP stays
    # locked down. In production nginx proxies to OpenStreetMap
    # (see proxy/nginx-common.conf). The local Flask dev server has no nginx,
    # so we provide an equivalent proxy here.
    @app.route("/maptiles/<int:z>/<int:x>/<int:y>.png")
    def dev_maptiles(z, x, y):
        try:
            upstream = requests.get(
                f"https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                headers={"User-Agent": "datagov-catalog-local-dev"},
                timeout=10,
            )
        except requests.RequestException as exc:
            logger.warning("Failed to fetch map tile", extra={"error": str(exc)})
            return Response(status=502)

        return Response(
            upstream.content,
            status=upstream.status_code,
            content_type=upstream.headers.get("Content-Type", "image/png"),
            headers={"Cache-Control": "public, max-age=86400"},
        )
