from flask import render_template

from app.blueprints.main import main_bp


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/split-pdf")
def split_pdf():
    return render_template("placeholder.html", title="Split PDF", heading="Split PDF", message="Under Development — splitting is coming soon.")
