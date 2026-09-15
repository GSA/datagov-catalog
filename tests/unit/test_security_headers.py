import base64
import hashlib
from pathlib import Path

from app import HSTS_HEADER, create_app
from app.filters import all_badge_colors


def test_https_responses_set_preload_ready_hsts_header():
    app = create_app("production")

    response = app.test_client().get(
        "/js/datetime.js", headers={"X-Forwarded-Proto": "https"}
    )

    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"] == HSTS_HEADER


def test_nginx_sets_hsts_header_for_base_domain_and_redirects():
    nginx_header = f'add_header Strict-Transport-Security "{HSTS_HEADER}" always;'

    primary_server_config = Path("proxy/nginx-common.conf").read_text()
    nginx_config = Path("proxy/nginx.conf").read_text()

    assert nginx_header in primary_server_config
    assert "proxy_hide_header Strict-Transport-Security;" in primary_server_config
    assert nginx_header in nginx_config


def test_csp_allowlists_every_resource_badge_color():
    """dataset_card.j2 etc. render style="background-color: <color>;" inline,
    so style-src-attr needs a hash source per color or the browser drops it."""
    app = create_app("production")
    response = app.test_client().get("/")
    csp = response.headers["Content-Security-Policy"]

    for color in all_badge_colors():
        digest = hashlib.sha256(f"background-color: {color};".encode()).digest()
        expected_hash = f"'sha256-{base64.b64encode(digest).decode()}'"
        assert expected_hash in csp
