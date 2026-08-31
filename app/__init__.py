from flask import Flask, jsonify, render_template, request

from app.config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register blueprints
    from app.blueprints.main import main_bp
    from app.blueprints.compress import compress_bp
    from app.blueprints.split import split_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(compress_bp)
    app.register_blueprint(split_bp)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(_error):
        # AJAX/fetch requests expect JSON; direct navigation expects HTML
        wants_json = (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in (request.headers.get("Accept") or "")
            or request.is_json
            or request.headers.get("Content-Type", "").startswith("multipart/form-data")
        )
        # For fetch() calls from compress.js/split.js (multipart/form-data), return JSON
        if wants_json:
            return jsonify({"error": "File is too large. Maximum allowed size is 50 MB."}), 413
        # Fallback: check if request is XHR-like via Accept header or if endpoint is known AJAX POST
        # Safer: if request path ends with compress/split and method is POST, prefer JSON
        if request.path in ("/compress-pdf", "/split-pdf") and request.method == "POST":
            return jsonify({"error": "File is too large. Maximum allowed size is 50 MB."}), 413
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def internal_error(_error):
        return render_template("errors/500.html"), 500

    return app
