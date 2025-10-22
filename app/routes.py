import json
import logging
from datetime import datetime
from math import ceil
from xml.etree import ElementTree

from dotenv import load_dotenv
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_sqlalchemy.query import Query

from . import htmx
from .database import DEFAULT_PAGE, DEFAULT_PER_PAGE, CatalogDBInterface
from .utils import build_dataset_dict, json_not_found, valid_id_required

logger = logging.getLogger(__name__)

main = Blueprint("main", __name__)

# Login authentication
load_dotenv()


STATUS_STRINGS_ENUM = {404: "Not Found"}

interface = CatalogDBInterface()


class UnsafeTemplateEnvError(RuntimeError):
    pass


def render_block(template_name: str, block_name: str, **context) -> Response:
    """
    Render a specific block from a Jinja template, while using the Flask's default environment.
    """
    env = current_app.jinja_env
    if not getattr(env, "autoescape", None):
        raise UnsafeTemplateEnvError(
            "Jinja autoescape is disabled; enable it or use Flask's jinja_env."
        )
    template = env.get_template(template_name)

    # Render only the named block (Jinja will still escape vars inside the block)
    block_gen = template.blocks[block_name]
    html = "".join(block_gen(template.new_context(context)))
    return Response(html, mimetype="text/html; charset=utf-8")


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


# Routes
@main.route("/", methods=["GET"])
def index():
    query = request.args.get("q", "")
    page = request.args.get("page", DEFAULT_PAGE, type=int)
    per_page = request.args.get("per_page", DEFAULT_PER_PAGE, type=int)
    org_id = request.args.get("org_id", None, type=str)
    org_types = request.args.getlist("org_type")
    sort_by = request.args.get("sort", "relevance")

    # Initialize empty results
    datasets = []
    total = 0
    total_pages = 1

    # Only search if there's a query
    if query:
        results = interface.search_datasets(
            query,
            page=page,
            per_page=per_page,
            paginate=False,
            count=True,
            include_org=True,
            org_id=org_id,
            org_types=org_types,
            sort_by=sort_by,
        )

        # Get total count
        total = results.count()

        # Apply pagination
        offset = (page - 1) * per_page
        results = results.limit(per_page).offset(offset).all()

        # Build dataset dictionaries with organization data
        datasets = [build_dataset_dict(result) for result in results]

        # Calculate total pages
        total_pages = max(ceil(total / per_page), 1) if per_page else 1

    return render_template(
        "index.html",
        query=query,
        datasets=datasets,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        page_sequence=build_page_sequence(page, total_pages),
        org_id=org_id,
        org_types=org_types,
        sort_by=sort_by,
    )


@main.route("/search", methods=["GET"])
def search():
    """Search for datasets.

    The search argument is `q`: `/search?q=search%20term`.
    """
    # missing query parameter searches for everything
    query = request.args.get("q", "")
    page = request.args.get("page", DEFAULT_PAGE, type=int)
    per_page = request.args.get("per_page", DEFAULT_PER_PAGE, type=int)
    org_id = request.args.get("org_id", None, type=str)
    org_types = request.args.getlist("org_type")
    results = interface.search_datasets(
        query,
        page=page,
        per_page=per_page,
        paginate=request.args.get("paginate", type=lambda x: x.lower() == "true"),
        count=request.args.get("count", type=lambda x: x.lower() == "true"),
        include_org=True,
        org_id=org_id,
        org_types=org_types,
    )

    if htmx:
        # type hint that this is a Query object because paginate returns a query
        #  if count is True.
        results: Query
        total = results.count()
        offset = (page - 1) * per_page
        results = results.limit(per_page).offset(offset).all()
        results = [build_dataset_dict(result) for result in results]
        total_pages = max(ceil(total / per_page), 1) if per_page else 1
        return render_template(
            "components/dataset_results.html",
            datasets=results,
            page=page,
            page_sequence=build_page_sequence(page, total_pages),
            total=total,
            total_pages=total_pages,
        )

    return jsonify([build_dataset_dict(result) for result in results])


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


@main.route("/organization", methods=["GET"])
def list_organizations():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)
    search_query = request.args.get("q", default="", type=str).strip()

    result = interface.list_organizations(
        page=page, per_page=per_page, search=search_query
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

    organization_data = interface.to_dict(organization)
    dataset_page = request.args.get("dataset_page", default=1, type=int)
    dataset_per_page = request.args.get("dataset_per_page", default=20, type=int)
    sort_by = request.args.get("sort", default="popularity")
    dataset_search_terms = request.args.get(
        "dataset_search_terms", default="", type=str
    ).strip()

    dataset_result = interface.list_datasets_for_organization(
        organization.id,
        page=dataset_page,
        per_page=dataset_per_page,
        sort_by=sort_by,
        dataset_search_terms=dataset_search_terms,
    )

    dataset_pagination = (
        {
            "page": dataset_result["page"],
            "per_page": dataset_result["per_page"],
            "total": dataset_result["total"],
            "total_pages": dataset_result["total_pages"],
            "page_sequence": build_page_sequence(
                dataset_result["page"], dataset_result["total_pages"]
            ),
        }
        if dataset_result["total"]
        else {
            "page": dataset_result["page"],
            "per_page": dataset_result["per_page"],
            "total": 0,
            "total_pages": 0,
            "page_sequence": [],
        }
    )

    if organization_data is not None:
        organization_data["dataset_count"] = dataset_result["total"]

    slug_or_id = organization.slug or slug

    return render_template(
        "organization_detail.html",
        organization=organization_data,
        datasets=dataset_result["datasets"],
        dataset_pagination=dataset_pagination,
        organization_slug_or_id=slug_or_id,
        selected_sort=dataset_result.get("sort", "popularity"),
        sort_options={
            "popularity": "Popularity",
            "slug": "Title (shhh...it is slug)",
            "harvested": "Harvested Date",
        },
        dataset_search_terms=dataset_search_terms,
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
    return render_template(
        "dataset_detail.html",
        dataset=dataset,
    )


def register_routes(app):
    app.register_blueprint(main)
