from pathlib import Path

from app import HSTS_HEADER, create_app


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
