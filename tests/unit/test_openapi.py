"""Test OpenAPI paths."""

from bs4 import BeautifulSoup

from app.search import API_CONTEXT, FILTERS


class TestOpenAPI:

    def test_openapi_json(self, db_client):
        """The OpenAPI spec can be downloaded."""
        resp = db_client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json
        assert spec["info"]["title"] == "Datagov Catalog"
        for top_level in ["info", "components", "paths", "openapi", "servers"]:
            assert top_level in spec

    def test_search_query_parameters_include_registered_api_filters(self, db_client):
        """The search API docs stay in sync with registered API filters."""
        resp = db_client.get("/openapi.json")
        assert resp.status_code == 200

        params = resp.json["paths"]["/search"]["get"]["parameters"]
        documented_names = {
            param["name"] for param in params if param.get("in") == "query"
        }
        registered_names = {
            api_param.name
            for definition in FILTERS
            if API_CONTEXT in definition.parse_contexts
            for api_param in definition.api_query_params
        }

        assert registered_names <= documented_names
        assert {"keyword", "geography_label"} <= documented_names

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
