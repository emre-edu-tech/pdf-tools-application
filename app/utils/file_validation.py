def is_valid_pdf(file_storage) -> bool:
    """
    Validate that the uploaded file looks like a PDF.

    Checks:
    - filename ends with .pdf (case-insensitive)
    - first 5 bytes are %PDF-
    - file is not empty

    The stream is reset to position 0 after reading so downstream code can read it fully.

    :param file_storage: Werkzeug FileStorage (or similar) with .filename and .stream
    :return: True if valid PDF, False otherwise
    """
    if file_storage is None:
        return False

    filename = getattr(file_storage, "filename", None)
    if not filename or not isinstance(filename, str):
        return False
    if not filename.lower().endswith(".pdf"):
        return False

    # Determine the underlying stream
    stream = getattr(file_storage, "stream", None)
    # Fallback: file_storage itself might be the stream (e.g. BytesIO passed in tests)
    if stream is None:
        # Try to treat file_storage as a file-like object
        stream = file_storage

    try:
        # Ensure we can seek/read
        if hasattr(stream, "seek"):
            stream.seek(0)
        else:
            return False

        # Check file is not empty by getting size
        # Use seek to end to get size, then seek back
        try:
            stream.seek(0, 2)
            size = stream.tell()
            if size == 0:
                return False
            stream.seek(0)
        except Exception:
            # If tell/seek fails, try reading
            stream.seek(0)
            data = stream.read()
            if len(data) == 0:
                return False
            stream.seek(0)
            # Header check will be done after; we already have data
            header = data[:5]
            # Reset
            stream.seek(0)
            return header == b"%PDF-"

        # Read first 5 bytes for magic check
        header = stream.read(5)
        # Important: reset for later use
        try:
            stream.seek(0)
        except Exception:
            pass

        if header != b"%PDF-":
            return False

        # Also ensure that if FileStorage wraps stream, its own read pointer is reset
        # Some Werkzeug versions need file_storage.seek(0) as well
        try:
            if hasattr(file_storage, "seek") and file_storage is not stream:
                file_storage.seek(0)
        except Exception:
            pass

        return True
    except Exception:
        try:
            if hasattr(stream, "seek"):
                stream.seek(0)
        except Exception:
            pass
        return False
