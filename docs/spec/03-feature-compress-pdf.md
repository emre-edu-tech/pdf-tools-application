# Step 3 — Compress PDF Feature (Full Stack)

## Session Goal
Implement the complete Compress PDF feature: upload UI, AJAX upload, backend compression by shelling out to the **Ghostscript** binary, and a working download — end to end.

## Context for the Agent
The project already has a working base layout, nav, and homepage (Steps 1–2). **Inspect `app/` before editing.** This step **owns the `compress` blueprint**: create `app/blueprints/compress/` (mirroring the `main` blueprint's structure: `__init__.py` + `routes.py`), register it in `create_app()`, and **entirely replace** the Step 2 placeholder `/compress-pdf` route and its "coming soon" template.

> **Library choice — Ghostscript (not pure-Python):** an earlier pure-Python approach (`pikepdf` recompressing images object-by-object, `Pillow` downsampling) was ditched for compression — it fell well short of the target ratio on image-heavy PDFs. This feature uses the **Ghostscript** system binary via `subprocess` + `pdfwrite` device instead (re-renders whole PDF in one pass, much closer to iLovePDF). Splitting (Step 4) separately uses `pypdf` (`PdfReader`/`PdfWriter`, pure Python, in-memory) — do not reintroduce `pikepdf`/`Pillow` here.

---

## Ghostscript Requirement — Install Before Development

This feature calls the **Ghostscript command-line binary** (`gs` / `gswin64c.exe`) via Python's `subprocess` module. It is **not** a pip package — it must be installed as a system binary on every machine that runs this code (dev machines and the production server). Install it first, and confirm it works from a terminal, before writing any code against it.

### Windows (local dev)
Install via the official installer at ghostscript.com ("Ghostscript AGPL Release"), which installs a console executable named **`gswin64c.exe`** (64-bit) or `gswin32c.exe` (32-bit) — not `gs.exe`. Make sure the install directory's `bin` folder is added to the system `PATH` so `gswin64c` is callable from any terminal. Verify with:
```
gswin64c --version
```

### macOS
Install via Homebrew:
```
brew install ghostscript
```
This installs the binary as `gs`, and Homebrew puts it on `PATH` automatically. Verify with:
```
gs --version
```

### Linux (Ubuntu/Debian — matches the production server)
Install via apt:
```
sudo apt-get update
sudo apt-get install ghostscript
```
This installs the binary as `gs`. Verify with:
```
gs --version
```
**Production note:** the app deploys under Phusion Passenger on Plesk. Passenger's process may not inherit the same shell `PATH` a normal SSH session has, so `shutil.which("gs")` could fail even though `gs --version` works fine over SSH. Confirm the app can actually find the binary in that environment (see the `GHOSTSCRIPT_BINARY` override below), and set an explicit absolute path (e.g. `/usr/bin/gs`, check with `which gs` over SSH) if auto-detection doesn't resolve it under Passenger.

---

## How Compression Works

The backend writes the uploaded PDF to a temporary file, calls Ghostscript's `pdfwrite` device as a subprocess to re-render the whole PDF (recompressing embedded images, subsetting fonts, and rebuilding the content streams), reads the result back, and cleans up the temp files. Ghostscript's `pdfwrite` device re-renders the entire PDF page description, so image downsampling, JPEG re-encoding, font subsetting, and stream recompression all happen together as one coherent pass — which is what tools like iLovePDF are built on top of.

**Files are processed via temp files, not in-memory streams.** Ghostscript's CLI operates on file paths — piping via stdin/stdout is unreliable across platforms (Windows in particular) and breaks on PDFs that need Ghostscript to seek within the input. Write the upload to a **temporary file** (via `tempfile`) and read Ghostscript's output from another temporary file, both inside a `tempfile.TemporaryDirectory()` that is deleted immediately after the request — in a `finally` block, so cleanup happens even if Ghostscript errors out. Nothing should persist on disk beyond the lifetime of a single request.

**Fixed settings for MVP** (no user-facing quality selector — documented stretch goal for later):
- `GS_PDFSETTINGS = "/ebook"` — Ghostscript's built-in "ebook" preset as the baseline (screen-resolution-ish images, good general compromise).
- Override on top of the preset for a more aggressive result:
  - `ColorImageResolution = 120` (dpi)
  - `GrayImageResolution = 120` (dpi)
  - `MonoImageResolution = 300` (dpi — monochrome/scanned-text images need to stay higher-res to stay legible)
  - `ColorImageDownsampleType = /Bicubic`, `GrayImageDownsampleType = /Bicubic`, `MonoImageDownsampleType = /Bicubic`
- `DetectDuplicateImages = true` — de-dupes repeated images (e.g. a logo on every page) instead of re-embedding them.
- `CompressFonts = true`, `SubsetFonts = true` — targets text-heavy PDFs (benchmarked against iLovePDF's 184 KB → 140 KB result) by shrinking font data instead of images.
- `AutoRotatePages = /None` — don't let Ghostscript auto-rotate pages based on detected text orientation; preserve the original page orientation exactly.
- `-dSAFER` — **security-relevant, not optional.** Disables PostScript file-system operators. Since this endpoint runs Ghostscript against untrusted user uploads, always pass `-dSAFER` to reduce the attack surface (Ghostscript has had real CVEs involving malicious PostScript/PDF content reaching the filesystem).
- `-dBATCH -dNOPAUSE -dQUIET` — required for unattended/non-interactive use; without these, Ghostscript can hang waiting for input (e.g. on a password-protected file) instead of erroring out.

**Known, intentional limitations for v1** (fine to build, just don't be surprised by them):
- Ghostscript compresses the whole PDF uniformly per the settings above — it handles per-image concerns like transparency/soft-masks correctly on its own, no extra logic needed.
- **Whole-file safety net:** after Ghostscript finishes, compare the compressed file's size to the original upload's size. If the "compressed" file isn't smaller, return the *original* file unchanged (with a message explaining the PDF was already optimized) rather than handing back a same-size-or-larger file labeled as compressed.
- A PDF that's already highly optimized, or very short/simple, may not shrink further — expected, and exactly what the safety net above is for.
- Ghostscript can be slow on very large or very image-heavy PDFs. Enforce a subprocess timeout so one huge upload can't hang the request indefinitely.

---

## Upload Size Limit & Client-Side Validation (Updated)

**Global limit is now 50 MB** (was 25 MB in earlier revisions). This applies to every upload endpoint (`/compress-pdf`, `/split-pdf`).

- **Backend:** `app/config.py` `Config.MAX_CONTENT_LENGTH = 50 * 1024 * 1024` (`52428800` bytes). `.env.example` `MAX_CONTENT_LENGTH=52428800`. Flask will automatically raise **413 Request Entity Too Large** when the request exceeds this. `app/__init__.py` must register a `@app.errorhandler(413)` that: for AJAX/`Accept: application/json` or `X-Requested-With: XMLHttpRequest` returns `jsonify({"error": "File is too large. Maximum allowed size is 50 MB."}), 413`, otherwise renders `errors/413.html` (same visual style as `404.html`/`500.html`, message "File too large — Maximum allowed size is 50 MB."). No file contents in logs.
- **Client-side (no round trip):** before any upload, check `file.size` against `MAX_BYTES = 50 * 1024 * 1024`. If `file.size > MAX_BYTES`, immediately show an inline error in `#error-area` — e.g. `"File is too large (12.3 MB). Maximum allowed size is 50 MB."` — hide the preview, keep the action button disabled, and **do not** call `fetch()`. The same check must also run on the Compress button click as a defensive second gate (in case the change event was bypassed). This gives the user instant feedback even before the server would return 413.
- Both layers are required: client check is UX (instant, no network), server check is security (cannot be bypassed).

---

## Tasks

1. **`app/services/compress_service.py`**:
   - Define `class CompressionError(Exception)`.
   - A helper to locate the Ghostscript binary:
      ```python
      import os, shutil, sys

      def _find_gs_binary() -> str:
          override = os.environ.get("GHOSTSCRIPT_BINARY")
          if override:
              return override
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
      ```
      Read `GHOSTSCRIPT_BINARY` from the environment (or from Flask config, whichever this project already uses for other env-driven settings) so production can pin an absolute path if `PATH` isn't reliable under Passenger.
   - `compress_pdf(input_stream) -> io.BytesIO`:
      - Create a `tempfile.TemporaryDirectory()`. Inside it, write `input_stream` to an `input.pdf` file.
      - Build and run the Ghostscript command via `subprocess.run(...)`, e.g.:
        ```python
        cmd = [
            gs_binary,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/ebook",
            "-dNOPAUSE", "-dBATCH", "-dQUIET", "-dSAFER",
            "-dDetectDuplicateImages=true",
            "-dCompressFonts=true", "-dSubsetFonts=true",
            "-dAutoRotatePages=/None",
            "-dColorImageDownsampleType=/Bicubic", "-dColorImageResolution=120",
            "-dGrayImageDownsampleType=/Bicubic", "-dGrayImageResolution=120",
            "-dMonoImageDownsampleType=/Bicubic", "-dMonoImageResolution=300",
            f"-sOutputFile={output_path}",
            input_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        ```
      - Wrap the call in `try/except subprocess.TimeoutExpired` → raise `CompressionError("This PDF took too long to compress and was skipped.")`.
      - After the call, check `result.returncode`:
        - If non-zero, inspect `result.stderr` (decoded, lowercased) for `"password"` → raise `CompressionError("This PDF is password-protected. Remove the password before compressing.")`.
        - Otherwise → raise `CompressionError("This file doesn't look like a valid PDF and couldn't be processed.")`.
      - If `returncode == 0` but the output file is missing or empty, treat that the same as a failure (raise the generic invalid-PDF `CompressionError`) — don't assume success just because the process exited cleanly.
      - On success, read the output file's bytes into an `io.BytesIO`, seek to `0`, and return it.
      - Clean up the temp directory in a `finally` block regardless of success or failure — nothing should be left on disk after the function returns.
   - Sanity-check the exact `subprocess`/Ghostscript flag behavior against the installed Ghostscript version if anything above doesn't match (flag names have been stable for a long time, but confirm with `gs --help` on the target machine), and pin the expected Ghostscript version in the README/docs (there's no `requirements.txt` entry for it since it's a system binary, not a pip package).

2. **`app/utils/file_validation.py`** (shared — reused by the Split feature): `is_valid_pdf(file_storage) -> bool` that checks (a) the filename ends in `.pdf`, (b) the first 5 bytes of the stream are `%PDF-` (read them, then `.seek(0)` to reset the stream for later use — this is important, don't forget it), and (c) the file isn't empty.

3. **`app/blueprints/compress/routes.py`**:
   - `GET /compress-pdf` → renders `compress.html`.
   - `POST /compress-pdf` (the AJAX endpoint) →
      - Validate the uploaded file with `is_valid_pdf`; on failure, return `{"error": "..."}` with HTTP 400.
      - On success, call `compress_pdf(file.stream)`. Compare the resulting size to the original upload's size; if not smaller, use the original bytes instead for the response (whole-file safety net above).
      - Return via `send_file(result_bytesio, mimetype="application/pdf", as_attachment=True, download_name=f"compressed-{secure_filename(original_filename)}")`.
      - Catch `CompressionError` → JSON error, 400, using its message directly (these messages are already written to be user-facing). Catch anything else unexpected (including a Ghostscript-not-found error surfaced as something other than `CompressionError`, if that can happen) → log server-side, return a generic 500 JSON error — never leak a raw stack trace or raw subprocess output to the client.
      - **Note:** oversized uploads (>50 MB) are rejected *before* this code runs by Flask's `MAX_CONTENT_LENGTH` → 413 handler (see `app/__init__.py` and Upload Size Limit section). Do not duplicate that check here, but ensure the 413 JSON path is tested end-to-end (see DoD).

4. **`app/templates/compress.html`** (extends `base.html`): page heading + one-line instructions, a styled native `<input type="file" accept="application/pdf">` (drag-and-drop is explicitly out of scope for v1 — a nicely styled native input is enough), helper text `"Only PDF files are supported. Max 50 MB."` (updated from 25 MB), a filename + file-size preview once a file is chosen, a "Compress" button (`bg-accent-600` CTA style) that's **disabled until a file is chosen and passes client-side size validation**, a loading state (spinner + disabled button + "Compressing…" text) shown while the request is in flight, and an inline error message area (`#error-area`) used for both size and server errors.

5. **`app/static/js/compress.js`**:
   - Define `const MAX_BYTES = 50 * 1024 * 1024` (52428800) — keep in sync with `app/config.py` / `.env.example`.
   - On file input `change`: do client-side checks **in this order** — (1) extension is `.pdf`, (2) `file.size > MAX_BYTES` → `showError("File is too large (X MB). Maximum allowed size is 50 MB.")`, hide preview, keep button disabled, return. Only if both pass, show filename/size, enable the Compress button. Use `formatSize()` to render the actual size in the error (e.g. `12.3 MB`).
   - On Compress click: re-validate extension **and** `file.size > MAX_BYTES` as a second gate (covers programmatic bypass). If too large, `showError(...)` and do not build `FormData`/`fetch()`. Otherwise build `FormData`, `fetch(POST /compress-pdf, ...)`, show loading state. On success (`response.ok`): Blob download as before. On failure: if `response.status === 413`, show `"File is too large. Maximum allowed size is 50 MB."` (even if server returned HTML, fall back to that message); else parse JSON error body. Always reset loading state in `finally`.
   - Also handle `fetch` rejection due to 413 HTML fallback gracefully — do not assume JSON is always returned.

6. Update `app/__init__.py`: register the new `compress` blueprint; remove the Step 2 placeholder route/template for `/compress-pdf`. Also ensure `MAX_CONTENT_LENGTH` is already 50 MB via `app/config.py`, and add `@app.errorhandler(413)` as described in Upload Size Limit section — it must return JSON for AJAX/fetch and HTML (`errors/413.html`) for direct navigation.

7. **`requirements.txt`**: no new pip package is needed for Ghostscript itself — it's a system binary, not installed via pip. Document the Ghostscript system dependency and the install commands above in the project README instead. (If the Split feature in Step 4 needs `pypdf` 6.1.x for page extraction, that's independent of this feature and stays in `requirements.txt` on its own merits — **do not reintroduce `pikepdf`/`Pillow` for compression**.)

8. **Config & env update (global, not just compress):** set `MAX_CONTENT_LENGTH = 50 * 1024 * 1024` in `app/config.py` and `MAX_CONTENT_LENGTH=52428800` in `.env.example` (and document in `README.md`). Create `app/templates/errors/413.html` (extends `base.html`, same card/centered style as `404.html`/`500.html`, title "File too large", message "File is too large. Maximum allowed size is 50 MB.") and ensure both `compress.html` and `split.html` show `Max 50 MB` and their JS files enforce the same client-side limit (keep the two features in sync).

## Definition of Done
- [ ] Uploading a real multi-page PDF with embedded photos and clicking Compress downloads a new PDF that opens correctly and is meaningfully smaller than the original
- [ ] Uploading a PDF that's mostly vector text (no large images) still downloads successfully and isn't made *larger* — the safety-net fallback returns the original in that case
- [ ] Uploading a non-PDF file (even one renamed with a `.pdf` extension) is rejected server-side with a clear error — the magic-byte check must actually catch this
- [ ] Uploading a password-protected PDF returns the specific, friendly `CompressionError` message rather than crashing or hanging
- [ ] Clicking Compress with no file selected can't happen (button stays disabled), and the server route also handles a missing file defensively without crashing
- [ ] Ghostscript is confirmed callable from the app on every target environment (Windows dev, and the Ubuntu/Plesk/Passenger production server specifically — don't assume `PATH` under Passenger matches an SSH session's `PATH`). No `pikepdf`/`Pillow` code remains for compression.
- [ ] No files persist on disk after a request completes — temp files are written for Ghostscript's sake but are always cleaned up, including on error paths
- [ ] A very large/slow PDF times out gracefully with a clear error instead of hanging the request indefinitely
- [ ] Selecting a file larger than **50 MB** shows an **immediate client-side warning** (no network request) — e.g. `"File is too large (52.1 MB). Maximum allowed size is 50 MB."` — keeps the Compress button disabled and hides the preview. The same check on button click prevents bypass. Server-side also rejects >50 MB with **413** (JSON `{"error": "File is too large. Maximum allowed size is 50 MB."}` for fetch, HTML `errors/413.html` for direct POST/navigation).
- [ ] `app/config.py` `MAX_CONTENT_LENGTH` is `50 * 1024 * 1024` and `.env.example` is `52428800`; `compress.html`/`split.html` hint says `Max 50 MB`; `compress.js`/`split.js` both enforce `MAX_BYTES = 52428800`
- [ ] Loading and error states are visually consistent with the design system from Step 2

## Out of Scope for This Step
- Do not touch the Split feature's core page-extraction logic — but do keep its **size limit + 413 handling + client warning** in sync with Compress (see task 8) so the two features share the same 50 MB behavior.
- Do not add a compression-quality selector — the fixed Ghostscript settings above only.
- Do not implement drag-and-drop upload.
- Do not attempt in-memory stdin/stdout piping to Ghostscript — use temp files as specified; it's the reliable, cross-platform choice.
