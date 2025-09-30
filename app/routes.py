import logging

from dotenv import load_dotenv
from flask import Blueprint, Response, current_app, render_template

logger = logging.getLogger(__name__)

user = Blueprint("user", __name__)
auth = Blueprint("auth", __name__)
main = Blueprint("main", __name__)
org = Blueprint("org", __name__)
source = Blueprint("harvest_source", __name__)
job = Blueprint("harvest_job", __name__)
api = Blueprint("api", __name__)
testdata = Blueprint("testdata", __name__)

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


def register_routes(app):
    app.register_blueprint(main)
