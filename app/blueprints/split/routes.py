import logging

from flask import jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from app.blueprints.split import split_bp
from app.services.split_service import SplitValidationError, split_pdf
from app.utils.file_validation import is_valid_pdf

logger = logging.getLogger(__name__)


@split_bp.route("/split-pdf", methods=["GET"])
def split_pdf_page():
    return render_template("split.html")


@split_bp.route("/split-pdf", methods=["POST"])
def split_pdf_action():
    if "file" not in request.files:
        return jsonify({"error": "No file was uploaded. Please select a PDF to split."}), 400

    file = request.files["file"]

    if not file or file.filename == "":
        return jsonify({"error": "No file was selected. Please choose a PDF."}), 400

    if not is_valid_pdf(file):
        return jsonify({"error": "Invalid PDF file. Please upload a valid PDF document."}), 400

    # Reset stream position after is_valid_pdf consumed it
    try:
        file.stream.seek(0)
    except Exception:
        try:
            file.seek(0)
        except Exception:
            pass

    # Parse from_page / to_page
    try:
        from_page = int(request.form.get("from_page", ""))
        to_page = int(request.form.get("to_page", ""))
    except (ValueError, TypeError):
        return jsonify({"error": "'From page' and 'to page' must be whole numbers."}), 400

    original_filename = file.filename or "document.pdf"

    try:
        result = split_pdf(file.stream, from_page, to_page)
    except SplitValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("Unexpected error during PDF split")
        return jsonify({"error": "An unexpected error occurred while splitting the PDF. Please try again."}), 500

    safe_name = secure_filename(original_filename) or "document.pdf"
    download_name = f"split-{from_page}-{to_page}-{safe_name}"

    return send_file(
        result,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_name,
    )
