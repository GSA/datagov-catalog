import pytest
from werkzeug.datastructures import MultiDict

from app.search.queries.criteria import SearchCriteria
from app.search.queries.filters.base import API_CONTEXT, MAIN_CONTEXT, FilterParseError


@pytest.mark.parametrize(
    "params",
    [
        [("spatial_filter", "badvalue")],
        [("org_type", "FakeType")],
        [
            ("org_type", "Federal Government"),
            ("org_type", "FakeType"),
        ],
    ],
)
def test_invalid_api_filter_values(params):
    with pytest.raises(FilterParseError):
        SearchCriteria.from_request_args(
            MultiDict(params),
            route_context=API_CONTEXT,
        )


@pytest.mark.parametrize(
    "params",
    [
        [("spatial_filter", "geospatial")],
        [("spatial_filter", "non-geospatial")],
        [("org_type", "Federal Government")],
    ],
)
def test_valid_api_filter_values(params):
    SearchCriteria.from_request_args(
        MultiDict(params),
        route_context=API_CONTEXT,
    )


def test_invalid_filter_remains_allowed_in_main_context():
    SearchCriteria.from_request_args(
        MultiDict([("spatial_filter", "badvalue")]),
        route_context=MAIN_CONTEXT,
    )


@pytest.mark.parametrize(
    "parameter,value",
    [
        ("spatial_filter", "badvalue"),
        ("org_type", "FakeType"),
    ],
)
def test_invalid_api_filter_returns_422(parameter, value):
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.get("/search", query_string={parameter: value})

    assert response.status_code == 422
    assert response.get_json()["error"] == "Search failed"
    assert parameter in response.get_json()["message"]


@pytest.mark.parametrize(
    "parameter",
    ["spatial_filter", "org_type"],
)
def test_empty_api_filter_is_ignored(parameter):
    criteria = SearchCriteria.from_request_args(
        MultiDict([(parameter, "")]),
        route_context=API_CONTEXT,
    )
    assert not criteria.has_active_filters()


@pytest.mark.parametrize(
    "parameter",
    ["spatial_filter", "org_type"],
)
def test_empty_api_filter_reaches_search_backend(parameter, monkeypatch):
    from app import create_app
    from app import routes

    app = create_app()
    app.config["TESTING"] = True

    class SearchReached(Exception):
        pass

    def fake_search(*args, **kwargs):
        raise SearchReached

    monkeypatch.setattr(routes.interface, "search_datasets", fake_search)

    with app.test_client() as client:
        with pytest.raises(SearchReached):
            client.get("/search", query_string={parameter: ""})


def test_malformed_spatial_geometry_returns_400():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.get(
            "/search",
            query_string={"spatial_geometry": "invalid-json"},
        )

    assert response.status_code == 400
