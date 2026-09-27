import io
import os
import shutil
import subprocess
import sys
import tempfile


class CompressionError(Exception):
    """Raised when PDF compression cannot proceed (password-protected, invalid PDF, etc.)."""

    pass


def _find_gs_binary() -> str:
    override = os.environ.get("GHOSTSCRIPT_BINARY")
    if override:
        return override
    # Also check Flask config if available (for Passenger where env may be via Flask)
    try:
        from flask import current_app

        if current_app:
            cfg_val = current_app.config.get("GHOSTSCRIPT_BINARY")
            if cfg_val:
                return cfg_val
    except Exception:
        pass
    candidates = ["gswin64c", "gswin32c"] if sys.platform == "win32" else ["gs"]
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    raise CompressionError(
        "Ghostscript isn't installed on this server. Install the Ghostscript "
        "binary and make sure it's on PATH, or set the GHOSTSCRIPT_BINARY "
        "environment variable to its full path."
    )


# Tuned 2026-09: forces JPEG re-encoding (AutoFilter off + DCTEncode) with
# QFactor 0.9, 96dpi color/gray, 300dpi mono. Verified 34.6MB slide deck -> ~3MB.
# NOTE: raising color/gray resolution toward 150dpi can cross Ghostscript's
# downsample threshold and silently disable compression (output ~= input size).
GS_DISTILLER_PARAMS = (
    "<< /ColorImageDict << /QFactor 0.9 /Blend 1 /HSample [2 1 1 2] /VSample [2 1 1 2] >> "
    "/GrayImageDict << /QFactor 0.9 /Blend 1 /HSample [2 1 1 2] /VSample [2 1 1 2] >> "
    ">> setdistillerparams"
)


def compress_pdf(input_stream) -> io.BytesIO:
    """
    Compress a PDF by shelling out to Ghostscript's pdfwrite device.

    Writes the uploaded PDF to a temporary file, calls Ghostscript to re-render
    it with aggressive compression settings, reads the result back into memory,
    and cleans up all temp files.

    :param input_stream: file-like object opened for reading (e.g. Flask's file.stream or BytesIO)
    :return: BytesIO seeked to 0 containing the compressed PDF
    :raises CompressionError: for password-protected, invalid PDFs, timeouts, or missing Ghostscript binary
    """
    gs_binary = _find_gs_binary()

    # Use TemporaryDirectory so Ghostscript can seek within input/output files.
    tmpdir_obj = tempfile.TemporaryDirectory()
    try:
        tmpdir = tmpdir_obj.name
        input_path = os.path.join(tmpdir, "input.pdf")
        output_path = os.path.join(tmpdir, "output.pdf")

        # Ensure input_stream is at start
        try:
            input_stream.seek(0)
        except Exception:
            pass

        # Read all bytes from input_stream
        try:
            data = input_stream.read()
        except Exception as exc:
            raise CompressionError("This file doesn't look like a valid PDF and couldn't be processed.") from exc

        # input_stream.read() may return None or str in edge cases
        if data is None:
            data = b""
        if isinstance(data, str):
            data = data.encode()

        if len(data) == 0:
            raise CompressionError("This file doesn't look like a valid PDF and couldn't be processed.")

        # Write input to temp file
        with open(input_path, "wb") as f:
            f.write(data)

        cmd = [
            gs_binary,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/ebook",
            "-dNOPAUSE",
            "-dBATCH",
            "-dQUIET",
            "-dSAFER",
            "-dDetectDuplicateImages=true",
            "-dCompressFonts=true",
            "-dSubsetFonts=true",
            "-dAutoRotatePages=/None",
            "-dCompressPages=true",
            "-dDownsampleColorImages=true",
            "-dDownsampleGrayImages=true",
            "-dDownsampleMonoImages=true",
            "-dColorImageDownsampleType=/Bicubic",
            "-dColorImageResolution=96",
            "-dGrayImageDownsampleType=/Bicubic",
            "-dGrayImageResolution=96",
            "-dMonoImageDownsampleType=/Bicubic",
            "-dMonoImageResolution=300",
            "-dAutoFilterColorImages=false",
            "-dColorImageFilter=/DCTEncode",
            "-dAutoFilterGrayImages=false",
            "-dGrayImageFilter=/DCTEncode",
            "-dColorConversionStrategy=/LeaveColorUnchanged",
            f"-sOutputFile={output_path}",
            "-c",
            GS_DISTILLER_PARAMS,
            "-f",
            input_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired as exc:
            raise CompressionError("This PDF took too long to compress and was skipped.") from exc
        except FileNotFoundError as exc:
            raise CompressionError(
                "Ghostscript isn't installed on this server. Install the Ghostscript "
                "binary and make sure it's on PATH, or set the GHOSTSCRIPT_BINARY "
                "environment variable to its full path."
            ) from exc

        # Decode combined stderr+stdout for error inspection (Ghostscript may write password/error to either stream)
        combined_text = ""
        try:
            stderr_decoded = result.stderr.decode("utf-8", errors="ignore") if result.stderr else ""
        except Exception:
            stderr_decoded = str(result.stderr) if result.stderr else ""
        try:
            stdout_decoded = result.stdout.decode("utf-8", errors="ignore") if result.stdout else ""
        except Exception:
            stdout_decoded = str(result.stdout) if result.stdout else ""
        combined_text = (stderr_decoded + " " + stdout_decoded).lower()

        # Password check takes precedence regardless of returncode (Ghostscript 10.x returns 0 but logs password to stderr/stdout)
        if "password" in combined_text:
            raise CompressionError("This PDF is password-protected. Remove the password before compressing.")

        if result.returncode != 0:
            raise CompressionError("This file doesn't look like a valid PDF and couldn't be processed.")

        # Even with returncode 0, Ghostscript can log "No pages will be processed" for truncated/invalid PDFs
        # while still producing a tiny output file. Treat that as invalid.
        if "no pages will be processed" in combined_text or "couldn't initialise file" in combined_text or "unrecoverable error" in combined_text:
            raise CompressionError("This file doesn't look like a valid PDF and couldn't be processed.")
        # Generic error string fallback when rc==0 but Ghostscript still reported an error
        if "error" in combined_text and combined_text.strip() != "":
            # Only trigger if output is suspiciously small or combined contains error keywords
            # Valid PDFs produce empty combined_text with -dQUIET, so this won't false-positive.
            raise CompressionError("This file doesn't look like a valid PDF and couldn't be processed.")

        # Check output file exists and is non-empty
        if not os.path.exists(output_path):
            raise CompressionError("This file doesn't look like a valid PDF and couldn't be processed.")
        try:
            out_size = os.path.getsize(output_path)
        except Exception:
            out_size = 0
        if out_size == 0:
            raise CompressionError("This file doesn't look like a valid PDF and couldn't be processed.")

        with open(output_path, "rb") as f:
            out_bytes = f.read()

        if len(out_bytes) == 0:
            raise CompressionError("This file doesn't look like a valid PDF and couldn't be processed.")

        output = io.BytesIO(out_bytes)
        output.seek(0)
        return output
    finally:
        try:
            tmpdir_obj.cleanup()
        except Exception:
            pass
