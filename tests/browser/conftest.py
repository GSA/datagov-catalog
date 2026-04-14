import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def base_url():
    return "http://localhost:8080/"
