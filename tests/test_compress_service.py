"""Smoke tests for the Ghostscript-based PDF compression feature.

Stdlib-only (unittest) + Flask test client. No extra pip packages needed.

Run from the project root with the venv interpreter::

    .\\venv\\Scripts\\python.exe -m unittest discover -s tests -v

Manual large-file checklist (needs a real ~30MB PDF, stdlib can't generate
image-heavy PDFs — use a local file, never commit it):

1. ``.\\venv\\Scripts\\python.exe -m unittest discover -s tests -v`` → all green.
2. Start the app (``.\\venv\\Scripts\\python.exe app.py``), upload the large PDF
   at http://127.0.0.1:5000/compress-pdf → a ``compressed-*.pdf`` downloads.
3. Compare sizes (see RECIPES below); expect roughly 5–10x smaller for
   photo/slide decks (e.g. 34.6MB → ~3MB). If output ~= input size, the
   safety net in ``app/blueprints/compress/routes.py`` returned the original:
   Ghostscript passed the images through (likely native resolution below the
   96dpi downsample threshold) — do NOT just raise the dpi, see RECIPES.
4. Open the download and eyeball text edges + photos for blur.
5. Check ``%TEMP%`` (Windows) / ``/tmp`` (Linux) for leftover ``tmp*`` dirs —
   there should be none (cleanup is in a ``finally`` block).

RECIPES (PowerShell, Ghostscript on PATH as ``gswin64c``):

    # Current app settings (baked into compress_service.py):
    gswin64c -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook `
      -dNOPAUSE -dBATCH -dQUIET -dSAFER -dDetectDuplicateImages=true `
      -dCompressFonts=true -dSubsetFonts=true -dAutoRotatePages=/None `
      -dCompressPages=true -dDownsampleColorImages=true `
      -dDownsampleGrayImages=true -dDownsampleMonoImages=true `
      -dColorImageDownsampleType=/Bicubic -dColorImageResolution=96 `
      -dGrayImageDownsampleType=/Bicubic -dGrayImageResolution=96 `
      -dMonoImageDownsampleType=/Bicubic -dMonoImageResolution=300 `
      -dAutoFilterColorImages=false -dColorImageFilter=/DCTEncode `
      -dAutoFilterGrayImages=false -dGrayImageFilter=/DCTEncode `
      -dColorConversionStrategy=/LeaveColorUnchanged `
      -sOutputFile=output-quality.pdf `
      -c "<< /ColorImageDict << /QFactor 0.9 /Blend 1 /HSample [2 1 1 2] /VSample [2 1 1 2] >> /GrayImageDict << /QFactor 0.9 /Blend 1 /HSample [2 1 1 2] /VSample [2 1 1 2] >> >> setdistillerparams" `
      -f "input.pdf"
"""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services import compress_service
from app.services.compress_service import CompressionError, compress_pdf


def make_minimal_pdf(text="Smoke test") -> bytes:
    """Build a tiny but structurally valid one-page PDF (no deps)."""
    content = f"BT /F1 24 Tf 100 700 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref_pos = len(pdf)
    pdf += b"xref\n0 %d\n" % (len(objects) + 1)
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += b"%010d 00000 n \n" % off
    pdf += (
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF"
        % (len(objects) + 1, xref_pos)
    )
    return bytes(pdf)


class CompressServiceTest(unittest.TestCase):
    def test_find_gs_binary(self):
        path = compress_service._find_gs_binary()
        self.assertTrue(path, "expected a Ghostscript binary path, got empty")

    def test_valid_pdf_returns_pdf(self):
        result = compress_pdf(io.BytesIO(make_minimal_pdf()))
        data = result.getvalue()
        self.assertTrue(data.startswith(b"%PDF-"), "output lacks %PDF- header")
        self.assertGreater(len(data), 0)

    def test_tuned_flags_present(self):
        """Guard the baked-in winning settings against regressions."""
        import inspect

        src = inspect.getsource(compress_service)
        for flag in (
            "-dAutoFilterColorImages=false",
            "-dColorImageFilter=/DCTEncode",
            "-dAutoFilterGrayImages=false",
            "-dGrayImageFilter=/DCTEncode",
            "-dColorImageResolution=96",
            "QFactor 0.9",
        ):
            self.assertIn(flag, src, f"missing tuned flag: {flag}")

    def test_invalid_bytes_raise(self):
        with self.assertRaises(CompressionError):
            compress_pdf(io.BytesIO(b"not a pdf at all"))

    def test_truncated_header_raises(self):
        with self.assertRaises(CompressionError):
            compress_pdf(io.BytesIO(b"%PDF-1.4 fake truncated"))

    def test_empty_raises(self):
        with self.assertRaises(CompressionError):
            compress_pdf(io.BytesIO(b""))

    def test_timeout_raises_friendly_error(self):
        with mock.patch.object(
            compress_service.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd="gs", timeout=60),
        ):
            with self.assertRaises(CompressionError) as ctx:
                compress_pdf(io.BytesIO(make_minimal_pdf()))
        self.assertIn("too long", str(ctx.exception))

    def test_missing_binary_raises_friendly_error(self):
        with mock.patch.dict(
            os.environ, {"GHOSTSCRIPT_BINARY": "nonexistent-gs-binary-xyz"}
        ):
            with self.assertRaises(CompressionError) as ctx:
                compress_pdf(io.BytesIO(make_minimal_pdf()))
        self.assertIn("Ghostscript", str(ctx.exception))

    def test_no_temp_dirs_leaked(self):
        before = set(os.listdir(tempfile.gettempdir()))
        compress_pdf(io.BytesIO(make_minimal_pdf()))
        try:
            compress_pdf(io.BytesIO(b"junk"))
        except CompressionError:
            pass
        after = set(os.listdir(tempfile.gettempdir()))
        self.assertEqual(before, after, f"temp leak: {after - before}")


class CompressRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_get_page_renders(self):
        resp = self.client.get("/compress-pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Compress PDF", resp.data)

    def test_post_valid_pdf_downloads(self):
        pdf = make_minimal_pdf()
        resp = self.client.post(
            "/compress-pdf",
            data={"file": (io.BytesIO(pdf), "smoke.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/pdf")
        self.assertIn("compressed-smoke.pdf", resp.headers.get("Content-Disposition", ""))
        self.assertTrue(resp.data.startswith(b"%PDF-"))

    def test_post_non_pdf_rejected(self):
        resp = self.client.post(
            "/compress-pdf",
            data={"file": (io.BytesIO(b"hello world"), "fake.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_post_missing_file(self):
        resp = self.client.post(
            "/compress-pdf", data={}, content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
