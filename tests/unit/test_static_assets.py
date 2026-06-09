import pytest

from app.static_assets import (
    DEFAULT_ASSET_VERSION,
    get_asset_version,
    static_url,
    unversion_static_filename,
    versioned_static_filename,
)


def test_get_asset_version_uses_env_var(monkeypatch):
    monkeypatch.setenv("ASSET_VERSION", "abc1234")
    assert get_asset_version() == "abc1234"


def test_get_asset_version_falls_back_to_dev_when_env_unset(monkeypatch):
    monkeypatch.delenv("ASSET_VERSION", raising=False)
    assert get_asset_version() == DEFAULT_ASSET_VERSION


@pytest.mark.parametrize("asset_version", ["../secret", "abc/123", "abc.123", ""])
def test_static_url_rejects_unsafe_asset_version(app, asset_version):
    app.config["ASSET_VERSION"] = asset_version

    with app.test_request_context("/"), pytest.raises(ValueError):
        static_url("js/filter_sidebar_toggle.js")


def test_get_asset_version_rejects_unsafe_env_var(monkeypatch):
    monkeypatch.setenv("ASSET_VERSION", "../secret")

    with pytest.raises(ValueError):
        get_asset_version()


def test_static_url_embeds_version_in_filename(app):
    app.config["ASSET_VERSION"] = "8eb9d3e"
    with app.test_request_context("/"):
        url = static_url("js/filter_sidebar_toggle.js")

    assert url.endswith("/js/filter_sidebar_toggle.8eb9d3e.js")
    assert "?v=" not in url


def test_static_url_preserves_existing_filename_dots(app):
    app.config["ASSET_VERSION"] = "8eb9d3e"
    with app.test_request_context("/"):
        url = static_url("assets/htmx/htmx.min.js")

    assert url.endswith("/assets/htmx/htmx.min.8eb9d3e.js")


def test_versioned_static_filename_maps_back_to_on_disk_filename():
    filename = "assets/htmx/htmx.min.js"

    versioned_filename = versioned_static_filename(filename, "8eb9d3e")

    assert versioned_filename == "assets/htmx/htmx.min.8eb9d3e.js"
    assert unversion_static_filename(versioned_filename, "8eb9d3e") == filename
    assert unversion_static_filename(filename, "8eb9d3e") == filename


def test_versioned_static_asset_request_serves_on_disk_file(app):
    app.config["ASSET_VERSION"] = "8eb9d3e"

    response = app.test_client().get("/js/datetime.8eb9d3e.js")

    assert response.status_code == 200
