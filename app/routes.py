import json
import logging
from datetime import datetime
from math import ceil

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

from .database import CatalogDBInterface
from .utils import json_not_found, valid_id_required

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
    """Display search page with results."""
    query = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    results = None
    if query:
        results = interface.search_harvest_records(
            query=query,
            status=status if status else None,
            page=page,
            per_page=per_page,
        )

    return render_template(
        "index.html",
        query=query,
        status=status,
        results=results,
    )


@main.route("/search", methods=["GET"])
def search():
    """Search for datasets.

    The search argument is `q`: `/search?q=search%20term`.
    """
    # missing query parameter searches for everything
    query = request.args.get("q", "")
    results = interface.search_datasets(
        query,
        page=request.args.get("page", type=int),
        per_page=request.args.get("per_page", type=int),
        paginate=request.args.get("paginate", type=lambda x: x.lower() == "true" ),
    )
    return jsonify([result.to_dict() for result in results])


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


@main.route("/harvest_record/", methods=["GET"])
def list_success_harvest_records():
    PER_PAGE = 20
    page = request.args.get("page", default=1, type=int)

    result = interface.list_success_harvest_record_ids(page=page, per_page=PER_PAGE)

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
        "harvest_record_list.html",
        record_ids=result["ids"],
        pagination=pagination,
    )


@main.route("/organization", methods=["GET"])
def list_organizations():
    interface = CatalogDBInterface()
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    result = interface.list_organizations(page=page, per_page=per_page)

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
    )


@main.route("/organization/<slug>", methods=["GET"])
def organization_detail(slug: str):
    interface = CatalogDBInterface()
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
    sources = [interface.to_dict(source) for source in organization.sources]

    return render_template(
        "organization_detail.html",
        organization=organization_data,
        sources=sources,
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
