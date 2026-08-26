# Step 4 — Split PDF Feature (Full Stack)

## Session Goal
Implement the complete Split PDF feature: from-page/to-page inputs, AJAX upload, backend page extraction, and a working download — end to end.

## Context for the Agent
The project already has a working base layout, nav, homepage, and a completed Compress feature (Steps 1–3). **Inspect `app/` before editing**, including `app/blueprints/compress/` and `app/utils/file_validation.py` — reuse their patterns for consistency. This step **owns the `split` blueprint**: create `app/blueprints/split/` (mirroring `compress/`'s structure), register it in `create_app()`, and **entirely replace** the Step 2 placeholder `/split-pdf` route and template. **Reuse** `app/utils/file_validation.py::is_valid_pdf` from Step 3 — do not duplicate it.

## How Splitting Works

Use **`pypdf`** (pure Python, no system dependency) — `PdfReader` / `PdfWriter`, fully in-memory via `io.BytesIO`. No temp files needed for this feature at all — simpler than Compress.

> **Note on tooling:** Compress uses Ghostscript, but Split deliberately stays on pypdf rather than switching to Ghostscript for consistency. Ghostscript can extract page ranges, but doing so here would mean giving up in-memory `BytesIO` processing (Ghostscript wants real file paths, reintroducing temp files), adding a separate step just to get a page count for validation, and parsing subprocess stderr instead of catching clean Python exceptions — with no compression/quality benefit to offset that, since Split doesn't transform page content. Revisit only if a single-external-tool footprint becomes a hard requirement later.

**Behavior:** the user enters a 1-indexed "from page" and "to page" (page 1 = the first page, matching how people read PDFs, not 0-indexed). The backend:
1. Reads the uploaded PDF with `PdfReader`, gets `total_pages = len(reader.pages)`.
2. Validates: both values are positive integers, `1 <= from_page <= to_page <= total_pages`.
3. On any failure, raises a specific, human-readable error for that exact case — e.g. *"This PDF only has 12 pages — 'to page' can't be 15."*, *"'From page' must be at least 1."*, *"'From page' can't be greater than 'to page'."*
4. On success, builds a `PdfWriter`, appends pages `from_page - 1` through `to_page - 1` (converting to pypdf's 0-indexing), writes to a `BytesIO`, and returns it positioned at `0`.

**Decision — keep this to one combined request.** File + `from_page` + `to_page` are all submitted together in a single AJAX call and validated server-side in one pass. Do **not** add a separate "upload first, then show me the page count" round trip — that's a documented stretch goal for later, not part of v1.

## Tasks

1. **`app/services/split_service.py`**: `split_pdf(file_stream, from_page: int, to_page: int) -> io.BytesIO`. Define and raise a custom `SplitValidationError(message)` for each validation failure described above, with the specific human-readable message. Returns a `BytesIO` ready to be read from the start on success.

2. **`app/blueprints/split/routes.py`**:
   - `GET /split-pdf` → renders `split.html`.
   - `POST /split-pdf` →
     - Validate the file with `is_valid_pdf` first (same pattern as Compress) → 400 JSON error on failure.
     - **Reset the stream position** (`file.stream.seek(0)`) immediately after `is_valid_pdf` runs — that check consumes the stream, so `PdfReader` needs to be handed a stream rewound to byte 0 or it will read as empty/corrupt.
     - Parse `from_page`/`to_page` from form data inside a `try/except` guarding against non-integer input → 400 JSON error if parsing fails (message: e.g. *"'From page' and 'to page' must be whole numbers."*).
     - Call `split_pdf()`; catch `SplitValidationError` → 400 JSON `{"error": message}` using its specific message.
     - On success, `send_file(result_bytesio, mimetype="application/pdf", as_attachment=True, download_name=f"split-{from_page}-{to_page}-{secure_filename(original_filename)}")`.
     - Catch anything else unexpected (e.g. `pypdf` raising on an encrypted/corrupt PDF) → log server-side, return HTTP **500** with a clear, non-crashing JSON error, not a stack trace.

3. **`app/templates/split.html`** (extends `base.html`): visually consistent with `compress.html` — same card/container pattern, same file-input styling and filename/size preview. Below the file input, two `type="number" min="1" step="1"` inputs side by side, labeled "From page" and "To page". A "Split" button, styled identically to the Compress button (`bg-accent-600` CTA). Same loading-state and inline-error-area pattern as Compress, so the two feature pages feel like one cohesive product.

4. **`app/static/js/split.js`**: mirrors `compress.js`'s structure — file selection handling and preview, plus **instant client-side checks with no server round trip** (from/to are positive integers, `from <= to`) shown the moment the user leaves either field or clicks Split. `FormData` submit including `from_page`/`to_page` alongside the file. Blob-download handling identical to `compress.js`. Same loading/error state pattern.

5. Update `app/__init__.py`: register the `split` blueprint; remove the Step 2 placeholder.

## Definition of Done
- [ ] Splitting a real multi-page PDF with a valid range downloads a new PDF containing exactly those pages, in the right order, and it opens correctly
- [ ] A single-page range (`from_page == to_page`) extracts exactly that one page
- [ ] Entering a "to page" beyond the PDF's actual page count shows the specific, server-validated error message — not a generic failure
- [ ] Entering "from" > "to" is caught instantly client-side (no server round trip needed) and is also validated server-side as a defensive backstop
- [ ] An encrypted or corrupt PDF is handled gracefully with a clear error message, not a crash or stack trace
- [ ] The Split page's visual style matches the Compress page exactly (same spacing, card, button styling)

## Out of Scope for This Step
- Do not touch the Compress feature or its blueprint.
- Do not add a "fetch page count after upload, before submit" round trip — single combined submission only.
- Do not support multiple or non-contiguous page ranges (e.g. `1-3,5,7-9`) — one contiguous range only.
