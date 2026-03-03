"""Test OpenAPI paths."""


class TestOpenAPI:

    def test_openapi_json(self, db_client):
        resp = db_client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json
        assert spec["info"]["title"] == "Datagov Catalog"
        for top_level in ["info", "components", "paths", "openapi", "servers"]:
            assert top_level in spec
