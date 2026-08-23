import io
import logging

from flask import jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from app.blueprints.compress import compress_bp
from app.services.compress_service import CompressionError, compress_pdf
from app.utils.file_validation import is_valid_pdf

logger = logging.getLogger(__name__)


@compress_bp.route("/compress-pdf", methods=["GET"])
def compress_pdf_page():
    return render_template("compress.html")


@compress_bp.route("/compress-pdf", methods=["POST"])
def compress_pdf_action():
    # Defensive: ensure file part exists
    if "file" not in request.files:
        return jsonify({"error": "No file was uploaded. Please select a PDF to compress."}), 400

    file = request.files["file"]

    if not file or file.filename == "":
        return jsonify({"error": "No file was selected. Please choose a PDF."}), 400

    # Validate PDF (extension + magic bytes + not empty)
    if not is_valid_pdf(file):
        return jsonify({"error": "Invalid PDF file. Please upload a valid PDF document."}), 400

    original_filename = file.filename or "document.pdf"

    # Capture original bytes and size for whole-file safety net
    try:
        file.stream.seek(0)
        original_bytes = file.stream.read()
        original_size = len(original_bytes)
        # Reset for compress_pdf
        file.stream.seek(0)
    except Exception:
        # Fallback via file.read
        try:
            file.seek(0)
            original_bytes = file.read()
            original_size = len(original_bytes)
            file.seek(0)
        except Exception:
            return jsonify({"error": "Could not read the uploaded file."}), 400

    if original_size == 0:
        return jsonify({"error": "The uploaded file is empty."}), 400

    # Use a BytesIO wrapper for the original bytes to ensure correct stream handling
    # compress_pdf expects a file-like object; we pass a fresh BytesIO
    input_stream = io.BytesIO(original_bytes)

    try:
        result = compress_pdf(input_stream)
    except CompressionError as e:
        # Use the user-facing message directly
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error during PDF compression")
        return jsonify({"error": "An unexpected error occurred while compressing the PDF. Please try again."}), 500

    # Whole-file safety net: if compressed file isn't smaller, return original
    try:
        result.seek(0, 2)
        compressed_size = result.tell()
        result.seek(0)
    except Exception:
        compressed_size = len(result.getvalue())
        result.seek(0)

    if compressed_size >= original_size:
        # Return original file unchanged – already optimized
        result = io.BytesIO(original_bytes)
        result.seek(0)
        # We could optionally add a header/message, but spec says return original bytes
        # The download will still happen; client can decide. The service logs that it's already optimized.
        # We keep filename as compressed- prefix as per spec, but could indicate not smaller.
        pass

    safe_name = secure_filename(original_filename) or "document.pdf"
    download_name = f"compressed-{safe_name}"

    return send_file(
        result,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_name,
    )
