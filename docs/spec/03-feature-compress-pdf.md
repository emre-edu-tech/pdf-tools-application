# Step 3 — Compress PDF Feature (Full Stack)

## Session Goal
Implement the complete Compress PDF feature: upload UI, AJAX upload, backend compression using pure-Python libraries, and a working download — end to end.

## Context for the Agent
The project already has a working base layout, nav, and homepage (Steps 1–2). **Inspect `app/` before editing.** This step **owns the `compress` blueprint**: create `app/blueprints/compress/` (mirroring the `main` blueprint's structure: `__init__.py` + `routes.py`), register it in `create_app()`, and **entirely replace** the Step 2 placeholder `/compress-pdf` route and its "coming soon" template.

## How Compression Works

No system binaries are used — everything runs through two pip-installable libraries:

- **`pikepdf`** (built on `qpdf`, MPL-2.0 license) — opens/saves the PDF, gives direct access to embedded image objects, and recompresses the PDF's internal container structure.
- **`Pillow`** (permissive license) — decodes each embedded image, downsamples it if it's larger than needed for on-screen viewing, and re-encodes it as a smaller JPEG.

**Why this combo, and not just `pypdf`/`pikepdf` alone:** the overwhelming majority of a PDF's file size usually comes from its embedded raster images (photos, scanned pages), not from the surrounding PDF structure. `pypdf` and `pikepdf` alone can tidy up the container (recompress content streams, drop unused objects) but don't touch image pixel data — that only saves a few percent on an image-heavy file. Pulling each image out, downsampling/re-encoding it with Pillow, and writing it back is what actually shrinks the file. This mirrors what Ghostscript's `/ebook` preset does internally, just implemented ourselves in pure Python.

**Fixed settings for MVP** (no user-facing quality selector — documented stretch goal for later):
- `JPEG_QUALITY = 60`
- `MAX_IMAGE_DIMENSION = 1600` (px, longest side — images bigger than this get downscaled)
- `MIN_IMAGE_DIMENSION_TO_PROCESS = 100` (px — skip small icons/logos, not worth recompressing and risks visible artifacting on tiny graphics)

**Known, intentional limitations for v1** (fine to build, just don't be surprised by them):
- Images with a soft mask (`/SMask`, i.e. transparency) are left untouched — flattening them to JPEG would destroy the transparency. Skipping is the safe choice.
- If an image fails to decode via Pillow (an unusual color space, etc.), leave it untouched rather than erroring out the whole request.
- If the recompressed version of a given image isn't actually smaller, keep the original image bytes for that image rather than swapping in a same-size-or-larger replacement.
- **Whole-file safety net:** after processing, compare the total output size to the original. If the "compressed" file isn't smaller, return the *original* file unchanged (with a message explaining the PDF was already optimized) rather than handing back a same-size-or-larger file labeled as compressed.

## Tasks

1. **`app/services/compress_service.py`**:
   - Define `class CompressionError(Exception)`.
   - `compress_pdf(input_stream) -> io.BytesIO`:
     - Open with `pikepdf.open(input_stream)`, catching `pikepdf.PasswordError` → raise `CompressionError("This PDF is password-protected. Remove the password before compressing.")`, and `pikepdf.PdfError` → raise `CompressionError("This file doesn't look like a valid PDF and couldn't be opened.")`.
     - Iterate `pdf.pages`, then each page's `page.images.values()`; for each image object, apply the recompression logic described above (skip if it has `/SMask`, skip if smaller than `MIN_IMAGE_DIMENSION_TO_PROCESS`, decode via `pikepdf.PdfImage(...).as_pil_image()`, downscale with `Image.thumbnail(...)` if needed, re-encode as JPEG via Pillow, and only call the object's `.write(jpeg_bytes, filter=pikepdf.Name("/DCTDecode"))` — updating `/ColorSpace`, `/BitsPerComponent`, `/Width`, `/Height` to match — if the result is actually smaller).
     - Save the whole PDF to a `BytesIO` using `pdf.save(output, compress_streams=True, stream_decode_level=pikepdf.StreamDecodeLevel.generalized, object_stream_mode=pikepdf.ObjectStreamMode.generate)` to also recompress the container/content streams.
     - Return the `BytesIO`, seeked to `0`.
   - Sanity-check the exact `pikepdf` API (method/argument names can shift slightly between versions) against the installed version's docs if anything above doesn't match — pin the version in `requirements.txt` either way so behavior doesn't drift later.

2. **`app/utils/file_validation.py`** (shared — will be reused by the Split feature in Step 4, so keep it generic): `is_valid_pdf(file_storage) -> bool` that checks (a) the filename ends in `.pdf`, (b) the first 5 bytes of the stream are `%PDF-` (read them, then `.seek(0)` to reset the stream for later use — this is important, don't forget it), and (c) the file isn't empty.

3. **`app/blueprints/compress/routes.py`**:
   - `GET /compress-pdf` → renders `compress.html`.
   - `POST /compress-pdf` (the AJAX endpoint) →
     - Validate the uploaded file with `is_valid_pdf`; on failure, return `{"error": "..."}` with HTTP 400.
     - On success, call `compress_pdf(file.stream)`. Compare the resulting size to the original upload's size; if not smaller, use the original bytes instead for the response (see the "whole-file safety net" above).
     - Return via `send_file(result_bytesio, mimetype="application/pdf", as_attachment=True, download_name=f"compressed-{secure_filename(original_filename)}")`.
     - Catch `CompressionError` → JSON error, 400, using its message directly (these messages are already written to be user-facing). Catch anything else unexpected → log server-side, return a generic 500 JSON error — never leak a raw stack trace to the client.

4. **`app/templates/compress.html`** (extends `base.html`): page heading + one-line instructions, a styled native `<input type="file" accept="application/pdf">` (drag-and-drop is explicitly out of scope for v1 — a nicely styled native input is enough), a filename + file-size preview once a file is chosen, a "Compress" button (`bg-accent-600` CTA style) that's **disabled until a file is chosen**, a loading state (spinner + disabled button + "Compressing…" text) shown while the request is in flight, and an inline error message area.

5. **`app/static/js/compress.js`**:
   - On file input `change`: do a light client-side sanity check (extension is `.pdf`), show filename/size, enable the Compress button.
   - On Compress click: build a `FormData`, `fetch(POST /compress-pdf, ...)`, show the loading state. On success (`response.ok`): read the response as a `Blob`, parse the filename from the `Content-Disposition` response header (fall back to a sensible default if parsing fails), create an object URL (`URL.createObjectURL`), build a temporary `<a download>` and `.click()` it to trigger the browser's save dialog, then `URL.revokeObjectURL(...)`. On failure: parse the JSON error body and show it in the error area. Always reset the loading state in a `finally` block.

6. Update `app/__init__.py`: register the new `compress` blueprint; remove the Step 2 placeholder route/template for `/compress-pdf`.

7. Add `pikepdf` and `Pillow` (pinned exact versions) to `requirements.txt`. No system packages or OS-level install steps are needed for either.

## Definition of Done
- [ ] Uploading a real multi-page PDF with embedded photos and clicking Compress downloads a new PDF that opens correctly and is meaningfully smaller than the original
- [ ] Uploading a PDF that's mostly vector text (no large images) still downloads successfully and isn't made *larger* — the safety-net fallback returns the original in that case
- [ ] Uploading a non-PDF file (even one renamed with a `.pdf` extension) is rejected server-side with a clear error — the magic-byte check must actually catch this
- [ ] Uploading a password-protected PDF returns the specific, friendly `CompressionError` message rather than crashing
- [ ] Clicking Compress with no file selected can't happen (button stays disabled), and the server route also handles a missing file defensively without crashing
- [ ] No files are written to disk at any point during processing — everything stays in memory
- [ ] Loading and error states are visually consistent with the design system from Step 2

## Out of Scope for This Step
- Do not touch the Split feature or its blueprint.
- Do not add a compression-quality selector — the fixed constants above only.
- Do not implement drag-and-drop upload.
