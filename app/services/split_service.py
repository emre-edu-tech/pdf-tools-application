import io

from pypdf import PdfReader, PdfWriter


class SplitValidationError(Exception):
    """Raised when split page range validation fails."""

    pass


def split_pdf(file_stream, from_page: int, to_page: int) -> io.BytesIO:
    """
    Extract pages from_page..to_page (1-indexed, inclusive) into a new PDF.

    :param file_stream: file-like object positioned at start (e.g. BytesIO or file.stream)
    :param from_page: 1-indexed start page (inclusive)
    :param to_page: 1-indexed end page (inclusive)
    :return: BytesIO seeked to 0 containing the extracted pages
    :raises SplitValidationError: for any invalid page range
    :raises Exception: for corrupt/encrypted PDFs (caller should map to 500)
    """
    # Ensure stream is at start
    try:
        file_stream.seek(0)
    except Exception:
        pass

    reader = PdfReader(file_stream)
    total_pages = len(reader.pages)

    # Validation: both must be positive integers
    # Note: type is int per spec, but we still guard
    if from_page < 1:
        raise SplitValidationError("'From page' must be at least 1.")
    if to_page < 1:
        raise SplitValidationError("'To page' must be at least 1.")
    if from_page > to_page:
        raise SplitValidationError("'From page' can't be greater than 'to page'.")
    if from_page > total_pages:
        raise SplitValidationError(
            f"This PDF only has {total_pages} pages \u2014 'from page' can't be {from_page}."
        )
    if to_page > total_pages:
        raise SplitValidationError(
            f"This PDF only has {total_pages} pages \u2014 'to page' can't be {to_page}."
        )

    writer = PdfWriter()
    for idx in range(from_page - 1, to_page):
        writer.add_page(reader.pages[idx])

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output
