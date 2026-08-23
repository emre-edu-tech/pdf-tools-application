from flask import Blueprint

compress_bp = Blueprint("compress", __name__)

from app.blueprints.compress import routes  # noqa: E402, F401
