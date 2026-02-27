import json
import logging
from collections.abc import Iterable
from datetime import datetime
from math import ceil
from urllib.parse import unquote
from xml.etree import ElementTree

from dotenv import load_dotenv
from flask import (
    Blueprint,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from . import htmx
from .database import DEFAULT_PER_PAGE, CatalogDBInterface
from .sitemap_s3 import (
    SitemapS3ConfigError,
    create_sitemap_s3_client,
    get_sitemap_s3_config,
)
from .utils import dict_from_hint, hint_from_dict, json_not_found, valid_id_required

logger = logging.getLogger(__name__)

main = Blueprint("main", __name__)

# Login authentication
load_dotenv()


STATUS_STRINGS_ENUM = {404: "Not Found"}

interface = CatalogDBInterface()


def _parse_bool_param(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "within"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "intersect", "intersects"}:
        return False
    return default


def build_page_sequence(cur: int, total_pages: int, edge: int = 1, around: int = 2):
    pages = []
    last = 0
    for num in range(1, total_pages + 1):
        if num <= edge or num > total_pages - edge or abs(num - cur) <= around:
            if last and num - last > 1:
                pages.append(None)
            pages.append(num)
            last = num
    return pages


SITEMAP_PAGE_SIZE = 10000
ALLOWED_SORTS = {"relevance", "popularity", "distance"}


def _homepage_dataset_total(default_total: int) -> int:
    """Return dataset total for the homepage, using the best available source."""

    methods_to_try = [
        getattr(interface, "count_all_datasets_in_search", None),
        getattr(interface, "total_datasets", None),
    ]

    for method in methods_to_try:
        if not callable(method):  # method may be stubbed or missing in tests
            continue
        try:
            total = method()
        except Exception:
            logger.exception("Failed to fetch dataset count for homepage")
            continue
        try:
            return int(total)
        except (TypeError, ValueError):
            logger.warning(
                "Dataset count is not numeric; falling back to search result total",
                extra={"count": total},
            )
            continue

    return default_total


def _normalize_sort(sort_value: str | None, spatial_geometry: dict | None) -> str:
    sort_key = (sort_value or "relevance").lower()
    if sort_key not in ALLOWED_SORTS:
        return "relevance"
    if sort_key == "distance" and spatial_geometry is None:
        return "relevance"
    return sort_key


def _collect_spatial_shapes(datasets: Iterable, limit: int = 20) -> list[dict]:
    """Return up to `limit` GeoJSON geometries from search results."""
    shapes: list[dict] = []
    for dataset in datasets:
        if not isinstance(dataset, dict):
            continue
        geometry = dataset.get("spatial_shape")
        if not isinstance(geometry, dict):
            continue
        if not geometry.get("type"):
            continue
        shapes.append(geometry)
        if len(shapes) >= limit:
            break
    return shapes


def _get_sitemap_body_or_404(bucket: str, key: str) -> bytes:
    """Fetch an object body from S3 or abort with 404 on any error."""
    s3 = create_sitemap_s3_client()
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()
    except Exception:
        abort(404)


@main.route("/sitemap.xml", methods=["GET"])
def sitemap_index() -> Response:
    """Fetch sitemap index from S3 and return as XML."""
    try:
        config = get_sitemap_s3_config()
    except SitemapS3ConfigError:
        abort(404)

    body = _get_sitemap_body_or_404(config.bucket, config.index_key)
    return Response(body, mimetype="application/xml")


@main.route("/sitemap/sitemap-<int:index>.xml", methods=["GET"])
def sitemap_chunk(index: int) -> Response:
    """Fetch a sitemap chunk file from S3 and return as XML."""
    if index < 0:
        abort(404)
    try:
        config = get_sitemap_s3_config()
    except SitemapS3ConfigError:
        abort(404)
    key = f"{config.prefix.rstrip('/')}/sitemap-{index}.xml"
    body = _get_sitemap_body_or_404(config.bucket, key)
    return Response(body, mimetype="application/xml")


# Routes
@main.route("/", methods=["GET"])
def index():
    """Home page is also the search results page.

    This page always loads the first results from the search. The number of
    results is specified by the `results` query parameter. HTMX on the page
    allows adding more results onto the page by using paging in the `/search`
    API in the background.

    """
    query = request.args.get("q", "")
    num_results = request.args.get("results", DEFAULT_PER_PAGE, type=int)
    org_slug_param = (request.args.get("org_slug", None, type=str) or "").strip()
    org_types = request.args.getlist("org_type")
    keywords = request.args.getlist("keyword")
    spatial_filter = request.args.get("spatial_filter", None, type=str)
    spatial_geometry = request.args.get("spatial_geometry", type=str)
    spatial_within = _parse_bool_param(request.args.get("spatial_within"), True)
    sort_by = request.args.get("sort", "relevance") or "relevance"
    # there's a limit on how many results can be requested
    num_results = min(num_results, 9999)

    if spatial_geometry is not None:
        try:
            # it's a URL parameter so it is probably URL-quoted
            spatial_geometry = json.loads(unquote(spatial_geometry))
        except json.JSONDecodeError:
            return (
                jsonify(
                    {
                        "error": "Search failed",
                        "message": "spatial_geometry parameter is malformed",
                    }
                ),
                400,
            )
    sort_by = _normalize_sort(sort_by, spatial_geometry)

    # Initialize empty results
    datasets: list[dict] = []
    result = None
    total = 0
    suggested_keywords = []
    suggested_organizations = []
    selected_organization = None
    org_filter_id = None

    if org_slug_param:
        try:
            selected_organization = interface.get_organization_by_slug(org_slug_param)
        except Exception:
            logger.exception(
                "Failed to resolve organization", extra={"org": org_slug_param}
            )
        else:
            if selected_organization:
                org_filter_id = selected_organization.id
            else:
                org_filter_id = org_slug_param

    has_filters = (
        query
        or org_types
        or keywords
        or org_filter_id
        or spatial_filter
        or spatial_geometry
    )

    try:
        result = interface.search_datasets(
            query,
            keywords=keywords,
            per_page=num_results,
            org_id=org_filter_id,
            org_types=org_types,
            sort_by=sort_by,
            spatial_filter=spatial_filter,
            spatial_geometry=spatial_geometry,
            spatial_within=spatial_within,
        )

        # For homepage without filters, get accurate total count
        result_total = result.total if result is not None else 0
        if not has_filters:
            total = _homepage_dataset_total(result_total)
        else:
            # For filtered searches, use the search result total (may be capped at 10k)
            total = result_total

    except Exception:
        logger.exception("Dataset search failed", extra={"query": query})
    else:
        # Build dataset dictionaries with organization data
        datasets = [each for each in result.results]

    if result is not None:
        after = result.search_after_obscured()
    else:
        after = None

    # Initialize contextual counts
    contextual_keyword_counts = {}
    contextual_org_counts = {}
    contextual_aggs = {"keywords": [], "organizations": []}

    # Get contextual aggregations based on current search parameters
    try:
        contextual_aggs = interface.get_contextual_aggregations(
            query=query,
            org_id=org_filter_id,
            org_types=org_types,
            keywords=keywords,
            spatial_filter=spatial_filter,
            spatial_geometry=spatial_geometry,
            keyword_size=100,
            org_size=100,
        )

        # Create lookup dictionaries for counts
        contextual_keyword_counts = {
            item["keyword"]: item["count"]
            for item in contextual_aggs.get("keywords", [])
        }
        contextual_org_counts = {
            item["slug"]: item["count"]
            for item in contextual_aggs.get("organizations", [])
        }
    except Exception:
        logger.exception("Failed to fetch contextual aggregations")

    # Always compute suggested keywords from contextual aggregations,
    # excluding any already-selected keywords so users can keep refining.
    try:
        keyword_items = sorted(
            contextual_aggs.get("keywords", []),
            key=lambda x: x["count"],
            reverse=True,
        )
        selected_keyword_set = set(keywords)
        suggested_keywords = [
            item["keyword"]
            for item in keyword_items
            if item["keyword"] not in selected_keyword_set
        ][:10]
    except Exception:
        logger.exception("Failed to fetch suggested keywords")

    # Always compute suggested organizations from contextual aggregations,
    # excluding the currently-selected organization.
    try:
        org_suggestions = interface.get_top_organizations(limit=100)
        # Add contextual counts to organizations
        for org in org_suggestions:
            org_slug = org.get("slug")
            if org_slug:
                org["dataset_count"] = contextual_org_counts.get(org_slug, 0)

        # Filter to only orgs with counts > 0 and sort by count
        org_suggestions = [
            org for org in org_suggestions if org.get("dataset_count", 0) > 0
        ]

        # Exclude the already-selected organization from suggestions
        if org_slug_param:
            org_suggestions = [
                org for org in org_suggestions if org.get("slug") != org_slug_param
            ]

        org_suggestions.sort(key=lambda x: x.get("dataset_count", 0), reverse=True)
        suggested_organizations = org_suggestions[:10]
    except Exception:
        logger.exception("Failed to fetch suggested organizations")

    # construct a from-string for this search to go into the dataset links
    from_hint = hint_from_dict(request.args)
    search_result_geometries = (
        _collect_spatial_shapes(datasets) if spatial_geometry is not None else []
    )
    return render_template(
        "index.html",
        query=query,
        results_hint=num_results,
        result_start_index=1,
        per_page=DEFAULT_PER_PAGE,
        after=after,
        datasets=datasets,
        total=total,
        org_slug=(
            selected_organization.slug if selected_organization else org_slug_param
        ),
        org_types=org_types,
        keywords=keywords,
        sort_by=sort_by,
        suggested_keywords=suggested_keywords,
        suggested_organizations=suggested_organizations,
        spatial_filter=spatial_filter,
        spatial_geometry=spatial_geometry,
        search_result_geometries=search_result_geometries,
        spatial_within=spatial_within,
        from_hint=from_hint,
        selected_organization=selected_organization,
        contextual_keyword_counts=contextual_keyword_counts,
        contextual_org_counts=contextual_org_counts,
    )


@main.route("/search", methods=["GET"])
def search():
    """Search for datasets.

    The search argument is `q`: `/search?q=search%20term`.
    """
    # missing query parameter searches for everything
    query = request.args.get("q", "")
    per_page = request.args.get("per_page", DEFAULT_PER_PAGE, type=int)
    results_hint = request.args.get("results", 0, type=int)
    from_hint = request.args.get("from_hint")
    org_slug_param = (request.args.get("org_slug", None, type=str) or "").strip()
    org_types = request.args.getlist("org_type")
    keywords = request.args.getlist("keyword")
    after = request.args.get("after")
    spatial_filter = request.args.get("spatial_filter", None, type=str)
    spatial_geometry = request.args.get("spatial_geometry", type=str)
    spatial_within = _parse_bool_param(request.args.get("spatial_within"), True)
    sort_by = request.args.get("sort", "relevance") or "relevance"

    selected_organization = None
    org_filter_id = None
    if org_slug_param:
        try:
            selected_organization = interface.get_organization_by_slug(org_slug_param)
        except Exception:
            logger.exception(
                "Failed to resolve organization", extra={"org": org_slug_param}
            )
        else:
            if selected_organization:
                org_filter_id = selected_organization.id
            else:
                org_filter_id = org_slug_param

    if spatial_geometry is not None:
        try:
            # it's a URL parameter so it is probably URL-quoted
            spatial_geometry = json.loads(unquote(spatial_geometry))
        except json.JSONDecodeError:
            return (
                jsonify(
                    {
                        "error": "Search failed",
                        "message": "spatial_geometry parameter is malformed",
                    }
                ),
                400,
            )
    sort_by = _normalize_sort(sort_by, spatial_geometry)

    # Use keyword search if keywords are provided
    result = interface.search_datasets(
        keywords=keywords,
        query=query,
        per_page=per_page,
        org_id=org_filter_id,
        org_types=org_types,
        spatial_filter=spatial_filter,
        spatial_geometry=spatial_geometry,
        spatial_within=spatial_within,
        after=after,
        sort_by=sort_by,
    )

    if htmx:
        results = [each for each in result.results]
        result_start_index = 1
        if results_hint and per_page:
            result_start_index = max(results_hint - per_page + 1, 1)
        if selected_organization:
            # specified organization so give org results
            return render_template(
                "components/dataset_results_organization.html",
                dataset_search_query=query,
                datasets=results,
                per_page=per_page,
                results_hint=results_hint,
                result_start_index=result_start_index,
                after=result.search_after_obscured(),
                selected_sort=sort_by,
                organization=selected_organization,
                organization_slug_or_id=selected_organization.slug,
                spatial_geometry=spatial_geometry,
                spatial_within=spatial_within,
            )
        return render_template(
            "components/dataset_results.html",
            query=query,
            datasets=results,
            per_page=per_page,
            results_hint=results_hint,
            result_start_index=result_start_index,
            from_hint=from_hint,
            after=result.search_after_obscured(),
            sort_by=sort_by,
            org_types=org_types,
            keywords=keywords,
            org_slug=(
                selected_organization.slug if selected_organization else org_slug_param
            ),
            spatial_filter=spatial_filter,
            spatial_geometry=spatial_geometry,
            spatial_within=spatial_within,
        )

    response_dict = {
        "results": [result for result in result.results],
        "sort": sort_by,
    }
    if result.search_after is not None:
        response_dict["after"] = result.search_after_obscured()
    return jsonify(response_dict)


@main.route("/harvest_record/<record_id>", methods=["GET"])
@valid_id_required
def get_harvest_record(record_id: str):
    record = interface.get_harvest_record(record_id)
    if record is None:
        return json_not_found()

    record_data = interface.to_dict(record)
    for key, value in record_data.items():
        if isinstance(value, datetime):
            record_data[key] = value.isoformat()

    source_raw = record_data.get("source_raw")
    if isinstance(source_raw, str) and source_raw:
        try:
            record_data["source_raw"] = json.loads(source_raw)
        except json.JSONDecodeError:
            pass

    return jsonify(record_data)


@main.route("/harvest_record/<record_id>/raw", methods=["GET"])
@valid_id_required
def get_harvest_record_raw(record_id: str) -> Response:
    """Return the raw payload stored on a harvest record.

    The endpoint fetches HarvestObject.source_raw and responds with a mimetype
    based on the payload content: application/json for valid JSON, application/xml
    for XML, and text/plain otherwise. A 404 JSON response is returned
    when the record does not exist or the payload is missing/empty.
    """
    record = interface.get_harvest_record(record_id)
    if record is None:
        return json_not_found()

    source_raw = record.source_raw
    if not source_raw:
        return json_not_found()

    if not isinstance(source_raw, str):
        source_raw = str(source_raw)

    mimetype = "text/plain"
    stripped_source = source_raw.strip()
    if stripped_source:
        try:
            json.loads(stripped_source)
        except (TypeError, json.JSONDecodeError):
            try:
                ElementTree.fromstring(stripped_source)
            except (ElementTree.ParseError, SyntaxError):
                # not JSON or XML, leave as "text/plain"
                pass
            else:
                mimetype = "application/xml"
        else:
            mimetype = "application/json"

    return Response(source_raw, mimetype=mimetype)


@main.route("/harvest_record/<record_id>/transformed", methods=["GET"])
@valid_id_required
def get_harvest_record_transformed(record_id: str) -> Response:
    """Return the transformed payload for a harvest record.

    The endpoint fetches HarvestObject.source_transform and
    returns the JSON content with the application/json mimetype.
    A 404 JSON response is returned if the record cannot be found,
    no transformed payload exists, or the stored payload is an empty string.
    """
    record = interface.get_harvest_record(record_id)
    if record is None:
        return json_not_found()

    transformed = record.source_transform
    if transformed is None:
        return json_not_found()

    if isinstance(transformed, str) and not transformed.strip():
        return json_not_found()

    body = json.dumps(transformed)
    return Response(body, mimetype="application/json")


@main.route("/organization", methods=["GET"], strict_slashes=False)
def list_organizations():
    page = request.args.get("page", default=1, type=int)
    # default 'per_page' of 24 is chosen to work well with different grid layouts
    # so on different devices the grid (3x3, 2x2, 1x1) is completely full
    per_page = request.args.get("per_page", default=24, type=int)
    search_query = request.args.get("q", default="", type=str).strip()

    result = interface.list_organizations(
        page=page, per_page=per_page, search=search_query, ignore_empty_orgs=True
    )

    total = result["total"]
    per_page = result["per_page"]
    current_page = max(result["page"], 1)
    total_pages = max(ceil(total / per_page), 1) if per_page else 1
    current_page = min(current_page, total_pages)

    pagination = {
        "page": current_page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "page_sequence": build_page_sequence(current_page, total_pages),
    }

    return render_template(
        "organization_list.html",
        organizations=result["organizations"],
        pagination=pagination,
        search_query=search_query,
    )


@main.route("/organization/<slug>", methods=["GET"])
def organization_detail(slug: str):
    organization = interface.get_organization_by_slug(slug)
    if organization is None:
        organization = interface.get_organization_by_id(slug)
        if organization is None:
            abort(404)
        if organization.slug and organization.slug != slug:
            return redirect(
                url_for("main.organization_detail", slug=organization.slug), code=302
            )

    dataset_search_query = request.args.get("q", default="", type=str).strip()
    num_results = request.args.get("results", default=DEFAULT_PER_PAGE, type=int)
    keywords = request.args.getlist("keyword")
    spatial_filter = request.args.get("spatial_filter", None, type=str)
    spatial_geometry = request.args.get("spatial_geometry", type=str)
    spatial_within = _parse_bool_param(request.args.get("spatial_within"), True)
    sort_by = request.args.get("sort", default="relevance")

    if spatial_geometry is not None:
        try:
            spatial_geometry = json.loads(unquote(spatial_geometry))
        except json.JSONDecodeError:
            return (
                jsonify(
                    {
                        "error": "Search failed",
                        "message": "spatial_geometry parameter is malformed",
                    }
                ),
                400,
            )
    sort_by = _normalize_sort(sort_by, spatial_geometry)

    suggested_keywords: list[str] = []
    if not keywords:
        try:
            suggested_keywords = interface.get_unique_keywords(size=10, min_doc_count=1)
            if suggested_keywords:
                suggested_keywords = [
                    keyword["keyword"] for keyword in suggested_keywords
                ]
        except Exception:
            logger.exception("Failed to fetch suggested keywords")

    dataset_result = interface.list_datasets_for_organization(
        organization.id,
        dataset_search_query=dataset_search_query,
        sort_by=sort_by,
        num_results=num_results,
        keywords=keywords,
        spatial_filter=spatial_filter,
        spatial_geometry=spatial_geometry,
        spatial_within=spatial_within,
    )
    after = dataset_result.search_after_obscured()
    search_result_geometries = (
        _collect_spatial_shapes(dataset_result.results)
        if spatial_geometry is not None
        else []
    )

    slug_or_id = organization.slug or slug

    # reassign organization dataset count from opensearch
    open_search_org_dataset_counts = interface.get_opensearch_org_dataset_counts(
        as_dict=True
    )
    organization.total_datasets = open_search_org_dataset_counts.get(slug_or_id, 0)

    return render_template(
        "organization_detail.html",
        organization=organization,
        datasets=dataset_result.results,
        num_matches=dataset_result.total,
        after=after,
        per_page=DEFAULT_PER_PAGE,
        results_hint=num_results,
        result_start_index=1,
        organization_slug_or_id=slug_or_id,
        selected_sort=sort_by,
        dataset_search_query=dataset_search_query,
        keywords=keywords,
        spatial_filter=spatial_filter,
        spatial_geometry=spatial_geometry,
        spatial_within=spatial_within,
        search_result_geometries=search_result_geometries,
        suggested_keywords=suggested_keywords,
    )


@main.route("/dataset/<slug_or_id>", methods=["GET"])
def dataset_detail_by_slug_or_id(slug_or_id: str):
    """Display dataset detail page by slug or ID."""
    dataset = interface.get_dataset_by_slug(slug_or_id)
    # if the dataset is not found by slug, try to find it by ID
    if dataset is None:
        dataset = interface.get_dataset_by_id(slug_or_id)
    # if the dataset is still not found, return 404
    if dataset is None:
        abort(404)

    # get the org for GA purposes so far
    org = interface.get_organization_by_id(dataset.organization_id) if dataset else None

    # Use from_hint to construct an arguments dict
    from_hint = request.args.get("from_hint")
    from_dict = dict_from_hint(from_hint)

    return render_template(
        "dataset_detail.html",
        dataset=dataset,
        organization=org,
        from_dict=from_dict,
    )


@main.route("/api/keywords", methods=["GET"])
def get_keywords_api():
    """API endpoint to get unique keywords with counts.

    Query parameters:
        size: Maximum number of keywords to return (default 100, max 1000)
        min_count: Minimum document count for keywords (default 1)

    Returns:
        JSON with list of keywords and their counts
    """
    size = request.args.get("size", 100, type=int)
    min_count = request.args.get("min_count", 1, type=int)

    # Validate parameters
    # Between 1 and 1000
    size = max(min(size, 1000), 1)
    # At least 1
    min_count = max(min_count, 1)

    try:
        keywords = interface.get_unique_keywords(size=size, min_doc_count=min_count)

        return jsonify(
            {
                "keywords": keywords,
                "total": len(keywords),
                "size": size,
                "min_count": min_count,
            }
        )
    except Exception as e:
        return jsonify({"error": "Failed to fetch keywords", "message": str(e)}), 500


@main.route("/api/organizations", methods=["GET"])
def get_organizations_api():
    """API endpoint to fetch organizations for autocomplete suggestions."""

    size = request.args.get("size", 100, type=int)
    size = max(min(size, 1000), 1)

    try:
        organizations = interface.get_top_organizations(limit=size)
        return jsonify(
            {
                "organizations": organizations,
                "total": len(organizations),
                "size": size,
            }
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to fetch organizations", "message": str(e)}),
            500,
        )


@main.route("/api/opensearch/health", methods=["GET"])
def get_opensearch_health_api():
    """API endpoint to fetch OpenSearch cluster health."""

    try:
        health = interface.opensearch.client.cluster.health()
        status = health.get("status") if isinstance(health, dict) else None
        return jsonify({"status": status})
    except Exception as e:
        logger.exception("Failed to fetch OpenSearch cluster health")
        return (
            jsonify(
                {
                    "status": "unknown",
                    "error": "Failed to fetch OpenSearch cluster health",
                    "message": str(e),
                }
            ),
            500,
        )


@main.route("/api/stats", methods=["GET"])
def get_stats_api():
    """Endpoint for stats consumers."""

    try:
        stats = interface.get_stats()
        return jsonify(stats)
    except Exception as e:
        logger.exception("Failed to fetch stats")
        return (
            jsonify({"error": "Failed to fetch stats", "message": str(e)}),
            500,
        )


@main.route("/api/locations/search", methods=["GET"])
def get_locations_api():
    """API endpoint to search location display names and ids.

    Query parameters:
        q: the text to search for in display names
        size: Maximum number of locations to return (default 100, max 2000)

    Returns:
        JSON with list of location display names and their ids
    """
    query = request.args.get("q", default="")
    size = request.args.get("size", 100, type=int)

    # Validate parameters
    # Between 1 and 1000
    size = max(min(size, 2000), 1)

    try:
        locations = [
            {
                key: value
                for key, value in loc.to_dict().items()
                if key in ["display_name", "id"]
            }
            for loc in interface.search_locations(query=query, size=size)
        ]

        return jsonify(
            {
                "locations": locations,
                "total": len(locations),
                "size": size,
            }
        )
    except Exception as e:
        return jsonify({"error": "Failed to fetch locations", "message": str(e)}), 400


@main.route("/api/location/<location_id>", methods=["GET"])
def get_location_by_id_api(location_id):
    """API endpoint to get geometry for one location

    Returns:
        JSON with at least a "geometry" with the location's GeoJSON.
    """
    location_obj = interface.get_location(location_id)
    if location_obj is None:
        return jsonify({"error": "Location not found"}), 404
    return jsonify(
        {
            "id": location_obj[0],
            "geometry": location_obj[1],
        }
    )


def register_routes(app):
    app.register_blueprint(main)
