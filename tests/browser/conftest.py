import pytest


@pytest.fixture(scope="session")
def base_url():
    return "http://localhost:8080/"


@pytest.fixture(autouse=True)
def desktop_viewport(page):
    """Use a desktop width so the filter sidebar is shown inline."""
    page.set_viewport_size({"width": 1280, "height": 900})
