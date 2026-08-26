from flask import Blueprint

split_bp = Blueprint("split", __name__)

from app.blueprints.split import routes  # noqa: E402, F401
