import logging

from dotenv import load_dotenv
from flask import Flask

logger = logging.getLogger(__name__)


load_dotenv()


def create_app():
    app = Flask(__name__, static_url_path="", static_folder="static")

    from .routes import register_routes

    register_routes(app)

    return app
