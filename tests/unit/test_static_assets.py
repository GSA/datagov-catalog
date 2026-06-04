from unittest.mock import Mock

from app.static_assets import DEFAULT_ASSET_VERSION, get_asset_version, static_url


def test_get_asset_version_uses_env_var(monkeypatch):
    monkeypatch.setenv("ASSET_VERSION", "abc1234")
    assert get_asset_version() == "abc1234"


def test_get_asset_version_falls_back_to_dev_when_git_unavailable(monkeypatch):
    monkeypatch.delenv("ASSET_VERSION", raising=False)

    def fail_git(*args, **kwargs):
        raise OSError("git not found")

    monkeypatch.setattr("app.static_assets.subprocess.run", fail_git)
    assert get_asset_version() == DEFAULT_ASSET_VERSION


def test_get_asset_version_uses_git_when_env_unset(monkeypatch):
    monkeypatch.delenv("ASSET_VERSION", raising=False)
    monkeypatch.setattr(
        "app.static_assets.subprocess.run",
        Mock(
            return_value=Mock(
                stdout="8eb9d3e\n",
            )
        ),
    )
    assert get_asset_version() == "8eb9d3e"


def test_static_url_appends_version_query(app):
    app.config["ASSET_VERSION"] = "8eb9d3e"
    with app.test_request_context("/"):
        url = static_url("js/filter_sidebar_toggle.js")

    assert url.endswith("?v=8eb9d3e")
    assert "/js/filter_sidebar_toggle.js" in url
