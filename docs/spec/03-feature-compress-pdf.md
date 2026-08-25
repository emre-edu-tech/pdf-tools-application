# Step 3 — Compress PDF Feature (Full Stack)

## Session Goal
Implement the complete Compress PDF feature: upload UI, AJAX upload, backend compression by shelling out to the **Ghostscript** binary, and a working download — end to end.

## Context for the Agent
The project already has a working base layout, nav, and homepage (Steps 1–2). **Inspect `app/` before editing.** This step **owns the `compress` blueprint**: create `app/blueprints/compress/` (mirroring the `main` blueprint's structure: `__init__.py` + `routes.py`), register it in `create_app()`, and **entirely replace** the Step 2 placeholder `/compress-pdf` route and its "coming soon" template.

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

4. **`app/templates/compress.html`** (extends `base.html`): page heading + one-line instructions, a styled native `<input type="file" accept="application/pdf">` (drag-and-drop is explicitly out of scope for v1 — a nicely styled native input is enough), a filename + file-size preview once a file is chosen, a "Compress" button (`bg-accent-600` CTA style) that's **disabled until a file is chosen**, a loading state (spinner + disabled button + "Compressing…" text) shown while the request is in flight, and an inline error message area.

5. **`app/static/js/compress.js`**:
   - On file input `change`: do a light client-side sanity check (extension is `.pdf`), show filename/size, enable the Compress button.
   - On Compress click: build a `FormData`, `fetch(POST /compress-pdf, ...)`, show the loading state. On success (`response.ok`): read the response as a `Blob`, parse the filename from the `Content-Disposition` response header (fall back to a sensible default if parsing fails), create an object URL (`URL.createObjectURL`), build a temporary `<a download>` and `.click()` it to trigger the browser's save dialog, then `URL.revokeObjectURL(...)`. On failure: parse the JSON error body and show it in the error area. Always reset the loading state in a `finally` block.

6. Update `app/__init__.py`: register the new `compress` blueprint; remove the Step 2 placeholder route/template for `/compress-pdf`.

7. **`requirements.txt`**: no new pip package is needed for Ghostscript itself — it's a system binary, not installed via pip. Document the Ghostscript system dependency and the install commands above in the project README instead. (If the Split feature in Step 4 needs `pikepdf` for page extraction, that's independent of this feature and stays in `requirements.txt` on its own merits.)

## Definition of Done
- [ ] Uploading a real multi-page PDF with embedded photos and clicking Compress downloads a new PDF that opens correctly and is meaningfully smaller than the original
- [ ] Uploading a PDF that's mostly vector text (no large images) still downloads successfully and isn't made *larger* — the safety-net fallback returns the original in that case
- [ ] Uploading a non-PDF file (even one renamed with a `.pdf` extension) is rejected server-side with a clear error — the magic-byte check must actually catch this
- [ ] Uploading a password-protected PDF returns the specific, friendly `CompressionError` message rather than crashing or hanging
- [ ] Clicking Compress with no file selected can't happen (button stays disabled), and the server route also handles a missing file defensively without crashing
- [ ] Ghostscript is confirmed callable from the app on every target environment (Windows dev, and the Ubuntu/Plesk/Passenger production server specifically — don't assume `PATH` under Passenger matches an SSH session's `PATH`)
- [ ] No files persist on disk after a request completes — temp files are written for Ghostscript's sake but are always cleaned up, including on error paths
- [ ] A very large/slow PDF times out gracefully with a clear error instead of hanging the request indefinitely
- [ ] Loading and error states are visually consistent with the design system from Step 2

## Out of Scope for This Step
- Do not touch the Split feature or its blueprint.
- Do not add a compression-quality selector — the fixed Ghostscript settings above only.
- Do not implement drag-and-drop upload.
- Do not attempt in-memory stdin/stdout piping to Ghostscript — use temp files as specified; it's the reliable, cross-platform choice.
