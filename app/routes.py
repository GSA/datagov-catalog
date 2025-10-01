import json
import logging
from datetime import datetime
from html import escape
from math import ceil

from dotenv import load_dotenv
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    url_for,
)

from .database import CatalogDBInterface

logger = logging.getLogger(__name__)

main = Blueprint("main", __name__)

# Login authentication
load_dotenv()


STATUS_STRINGS_ENUM = {404: "Not Found"}


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


# Routes
@main.route("/", methods=["GET"])
def index():
    """Render the index page"""
    return render_template("index.html")


@main.route("/harvest_record/<record_id>", methods=["GET"])
def get_harvest_record(record_id: str):
    interface = CatalogDBInterface()
    record = interface.get_harvest_record(record_id)
    if record is None:
        abort(404, description="HarvestRecord not found")

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

    interface = CatalogDBInterface()
    result = interface.list_success_harvest_record_ids(page=page, per_page=PER_PAGE)

    # no template yet, so build HTML manually
    response_html = ["<ul>"]
    for record_id in result["ids"]:
        safe_id = escape(record_id)
        record_url = url_for("main.get_harvest_record", record_id=record_id)
        response_html.append(f'<li><a href="{record_url}">{safe_id}</a></li>')
    response_html.append("</ul>")

    total = result["total"]
    per_page = result["per_page"]
    current_page = max(result["page"], 1)
    total_pages = max(ceil(total / per_page), 1) if per_page else 1
    current_page = min(current_page, total_pages)

    def build_page_sequence(cur: int, total_pages: int, edge: int = 1, around: int = 2):
        pages = []
        last = 0
        for num in range(1, total_pages + 1):
            if (
                num <= edge
                or num > total_pages - edge
                or abs(num - cur) <= around
            ):
                if last and num - last > 1:
                    pages.append(None)
                pages.append(num)
                last = num
        return pages

    response_html.append('<nav class="pagination">')
    response_html.append("<ul>")

    def page_link(label: str, target_page: int, is_disabled: bool = False, is_active: bool = False) -> None:
        if is_disabled:
            response_html.append(f'<li class="disabled"><span>{label}</span></li>')
            return
        if is_active:
            response_html.append(f'<li class="active"><span>{label}</span></li>')
            return
        query_args = request.args.to_dict()
        query_args["page"] = target_page
        link = url_for("main.list_success_harvest_records", **query_args)
        response_html.append(f'<li><a href="{link}">{label}</a></li>')

    page_link("&laquo;", current_page - 1, is_disabled=current_page <= 1)

    for page_number in build_page_sequence(current_page, total_pages):
        if page_number is None:
            response_html.append('<li class="ellipsis"><span>…</span></li>')
        else:
            page_link(str(page_number), page_number, is_active=page_number == current_page)

    page_link("&raquo;", current_page + 1, is_disabled=current_page >= total_pages)

    response_html.append("</ul>")
    response_html.append("</nav>")

    return Response("".join(response_html), mimetype="text/html")


def register_routes(app):
    app.register_blueprint(main)
