from flask import Flask, render_template

from app.config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register blueprints
    from app.blueprints.main import main_bp
    from app.blueprints.compress import compress_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(compress_bp)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(_error):
        return render_template("errors/500.html"), 500

    return app
