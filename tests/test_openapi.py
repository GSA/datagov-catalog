"""Test OpenAPI paths."""

from bs4 import BeautifulSoup

class TestOpenAPI:

    def test_openapi_json(self, db_client):
        """The OpenAPI spec can be downloaded."""
        resp = db_client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json
        assert spec["info"]["title"] == "Datagov Catalog"
        for top_level in ["info", "components", "paths", "openapi", "servers"]:
            assert top_level in spec

    def test_openapi_docs(self, db_client):
        """The Swagger docs can be loaded."""
        response = db_client.get("/openapi/docs")
        assert "OpenAPI Documentation" in response.text
        soup = BeautifulSoup(response.text, "html.parser")
        assert soup.find("div", id="swagger-ui") is not None
        assert any(
            "swagger-ui-bundle.js" in script_el.get("src", "")
            for script_el in soup.find_all("script")
        )
