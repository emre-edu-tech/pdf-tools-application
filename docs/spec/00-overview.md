# PDF Toolkit — Application Design & Development System

This is the master reference for building **PDF Toolkit**, a small Flask web app that bundles simple PDF utilities behind a clean, consistent UI. It is not meant to be fed to the coding agent in one shot — it's your own reference. The numbered files (`01-...` through `05-...`) are the actual per-session prompts.

## 1. Project Summary

A lightweight, self-hosted web tool with:

1. **Compress PDF** (`/compress-pdf`) — reduce a PDF's file size.
2. **Split PDF** (`/split-pdf`) — extract a page range (`from page` → `to page`) into a new PDF.

Built to be extended later with more PDF tools (merge, watermark, PDF↔image, etc.), so the architecture uses one Flask **blueprint per feature** from the start, even though there are only two today.

## 2. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Flask 3.1.x (latest stable 3.x) | App factory + blueprints pattern |
| PDF splitting | `pypdf` 6.16.x | Pure Python, in-memory, no system dependency |
| PDF compression | Ghostscript (system binary), invoked via `subprocess` | Re-renders the whole PDF via the `pdfwrite` device — image downsampling, font subsetting, and stream recompression in one pass — see Step 3 |
| Styling | Tailwind CSS **v3 LTS** (3.4.x), installed via npm | Not the CDN build — compiled locally |
| Frontend interactivity | Vanilla JS, `fetch()` + `FormData`, no framework | AJAX uploads, no full page reloads |
| Env management | Python `venv` (mandatory) + `python-dotenv` | `.env` for secrets/config |
| Package pinning | Exact versions in `requirements.txt` and `package.json` | Reproducible installs — doesn't apply to Ghostscript itself, since it isn't a pip package (see below) |

**Ghostscript is a required system-level binary — the one exception to "everything's a pip install."** `pypdf` ships as a self-contained pip wheel with no system dependency, but Ghostscript has to be installed separately on every machine that runs this app: Windows (`gswin64c.exe`), macOS (`brew install ghostscript` → `gs`), and the production Ubuntu/Plesk server (`apt-get install ghostscript` → `gs`). Exact install commands per platform are in Step 3.

This was a deliberate choice, made after an earlier pure-Python attempt (`pikepdf` recompressing images object-by-object, `Pillow` downsampling them) fell well short of the target compression ratio on image-heavy PDFs. Ghostscript's `pdfwrite` device re-renders the whole PDF as one coherent pass and gets much closer to what a service like iLovePDF produces.

**AGPL license note:** Ghostscript is licensed under the AGPL, which requires that if it's run as part of a network service, the complete corresponding source of the whole service be made available to anyone interacting with it over the network. That's satisfied here — this project is published as open source on GitHub — so there's no additional obligation beyond keeping the repo public.

## 3. MVP Feature Scope

In scope now: Compress PDF, Split PDF (single contiguous range).

Explicitly **out of scope** for v1 (documented, not built): merge PDFs, multi-range split (e.g. `1-3,5,7-9`), a compression-quality selector, drag-and-drop upload, PDF↔image conversion, OCR, watermarking, page count preview before submit. These are noted so nobody — including the coding agent — accidentally scope-creeps into them.

## 4. Architecture at a Glance

- **App factory** (`create_app()`) + one **blueprint per feature** (`main`, `compress`, `split`).
- **Stateless, no persistent file storage — temp files only where the tool requires them.** Splitting is fully in-memory: `pypdf` reads from and writes to `io.BytesIO` natively, so there's no `tempfile.TemporaryDirectory()` anywhere in the split blueprint. Compression is the one exception — Ghostscript's CLI needs real file paths, so the compress service writes the upload to a `tempfile.TemporaryDirectory()`, runs Ghostscript against it, reads the result back into memory, and deletes the temp directory in a `finally` block before the request completes. Either way, nothing persists past the lifetime of a single request — see Step 3 for the exact pattern.
- **Tailwind CLI build step**: `static/css/src/input.css` → compiled to `static/css/dist/output.css`, linked directly from templates. No Flask-Assets, no bundler beyond the Tailwind CLI.
- **AJAX flow**: JS submits `FormData` via `fetch()`; the server returns the processed PDF binary directly (`Content-Type: application/pdf`, `Content-Disposition: attachment`); JS reads it as a `Blob`, creates an object URL, and triggers the browser's save dialog. No server-side "processed file" storage or download tokens needed.

## 5. Folder Structure

Everything below lives **directly in the project root** you already have open — there's no wrapping `pdf-toolkit/` folder to create first. Step 1 explicitly tells the agent this.

```
app/
├── __init__.py            # create_app(), blueprint registration, error handlers
├── config.py              # loads .env via python-dotenv
├── blueprints/
│   ├── main/               (Step 1–2: index, nav, error pages)
│   ├── compress/            (Step 3)
│   └── split/                (Step 4)
├── services/
│   ├── compress_service.py  (Step 3)
│   └── split_service.py     (Step 4)
├── utils/
│   └── file_validation.py  # shared is_valid_pdf() — built in Step 3, reused in Step 4
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── compress.html
│   ├── split.html
│   ├── partials/ (nav.html, footer.html, flash.html)
│   └── errors/ (404.html, 500.html, 413.html)
└── static/
    ├── css/ (src/input.css, dist/output.css — generated)
    ├── js/ (common.js, compress.js, split.js)
    └── img/
.env.example
.gitignore
package.json
tailwind.config.js
requirements.txt
app.py                      # local dev entry point — run with `python app.py`
wsgi.py                     # deployment entry point for Plesk + Phusion Passenger only
README.md
```

**Two entry points, two purposes:**
- **`app.py`** — what you run locally: `python app.py`. Creates the app via `create_app()` and calls `app.run(debug=True)`.
- **`wsgi.py`** — used only when deploying to a Plesk server running Phusion Passenger. This is adapted from a known-working `wsgi.py` from one of your other Plesk/Passenger deployments, updated for the app factory pattern:

```python
import sys
import os

# Set the project root directory
project_home = os.path.dirname(__file__)
sys.path.insert(0, project_home)

# Set Python interpreter to your venv
INTERP = os.path.join(project_home, "venv", "bin", "python3")
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

# Import the app factory and create the application instance
from app import create_app

application = create_app()
```

The only change from the original was the last two lines — the original imported an already-created Flask instance directly (`from app import app as application`), which only works when everything lives in one flat `app.py`. Here, `app` is a package built around `create_app()`, so `wsgi.py` imports the factory and calls it itself.

**Why that one-line swap is actually sufficient, not just a cosmetic fix:**
- The interpreter re-exec (`os.execl`) still has to run *before* anything Flask-related loads — and it does, because `from app import create_app` is the line that first triggers Flask (and later, `pypdf`, once the split blueprint's modules import it) to load, whether that happens via top-level imports in `app/__init__.py` or inside `create_app()` itself. Since that import line comes strictly after the `os.execl` check in `wsgi.py`, the venv switch always happens first, exactly like in the original non-factory file.
- `create_app()` still only runs once. `os.execl` *replaces* the current process outright (not a fork/subprocess) — so if the interpreter doesn't match, execution never reaches the import line at all; it restarts from the top of `wsgi.py` under the correct interpreter, and *that* run is the one that reaches `from app import create_app` and calls it. There's no path where `create_app()` fires twice or where blueprints/config get double-registered.
- Everything the factory pattern adds — blueprint registration, config loading from `.env` — is now encapsulated inside `create_app()` itself, so calling it once and handing the result to `application` is a complete equivalent of the original's "import an already-built instance."

If you ever change `create_app()` to take an argument (e.g. an explicit `create_app("production")` for environment-specific config), `wsgi.py` would need `application = create_app("production")` instead — but as specified now, `create_app()` takes no arguments and reads everything from `.env`, so the parameterless call above is correct as-is.

**This file is Plesk-server-specific and won't run locally** — the `venv/bin/python3` path is a Linux/macOS venv layout, so on a Windows dev machine (or before a `venv/` even exists) the interpreter re-exec will fail outright. That's expected: `wsgi.py` is only ever meant to run once Passenger loads it on the actual (Linux) server, never on your machine. Step 1 doesn't test-run it locally for that reason. **Ghostscript itself must also be installed on that Plesk server** (see Step 3) — `wsgi.py` switching interpreters doesn't help if the `gs` binary isn't reachable from Passenger's process; confirm that separately, since Passenger may not inherit the same `PATH` an SSH session sees.

## 6. Design System

**Palette** — light background, ink-navy as the dark anchor color, a teal accent for calls to action:

| Token | Hex | Used for |
|---|---|---|
| `ink-900` | `#101B33` | Nav/header background, primary headings on light bg |
| `ink-700` | `#2E3A57` | Secondary dark accents, icon strokes |
| `ink-100` | `#E4E9F2` | Card borders |
| `ink-50` | `#F4F6FA` | Section backgrounds |
| `accent-600` | `#0D9488` | Primary CTA buttons (Compress, Split), links, focus rings |
| `accent-400` | `#3DBBA9` | Hover states, active nav underline |
| `gray-900` | `#111827` | Body headings (Tailwind default) |
| `gray-600` | `#4B5563` | Body/secondary text (Tailwind default) |
| `gray-50` / white | — | Page background |
| `red-600` / `amber-500` / `green-600` | — | Error / warning / success states (Tailwind defaults, no custom tokens needed) |

**Typography:** system font stack (Tailwind's default `font-sans`) — no external font import, keeps the app fully self-hosted with zero CDN calls.

**Components:**
- **Buttons (primary/CTA):** `bg-accent-600 hover:bg-accent-700 text-white rounded-lg px-5 py-2.5 font-medium transition`
- **Cards:** `bg-white border border-ink-100 rounded-xl p-6 hover:shadow-md hover:border-accent-300 transition`
- **Nav:** `bg-ink-900 text-white`, active link in `accent-400`

Exact Tailwind config code is given in Step 2.

## 7. Global Engineering Conventions

- App factory pattern; one blueprint per feature.
- `.env` / `.env.example` for all config and secrets — nothing hardcoded, nothing committed.
- `requirements.txt` and `package.json` use pinned, exact versions.
- Uploaded/processed files stay in memory (`io.BytesIO`) wherever the tool allows it — true for the entire Split flow. Compression is the exception: Ghostscript requires real file paths, so it uses ephemeral temp files that are always cleaned up in a `finally` block and never persist past a single request (see Step 3).
- Ghostscript's tested version isn't pinned via `requirements.txt` — it's a system binary, not a pip package. Document the version you built/tested against in `README.md` instead.
- `MAX_CONTENT_LENGTH` set in Flask config to reject oversized uploads early.
- Validate uploads by **both** extension and magic bytes (`%PDF-`) — never trust filename or MIME type alone.
- `werkzeug.utils.secure_filename()` on any filename that reaches a response header or the filesystem.
- AJAX endpoints return a consistent JSON error shape: `{"error": "human-readable message"}`, with proper HTTP status codes (400 validation, 413 too large, 500 unexpected).
- No file contents in logs — metadata only.

## 8. Session / Step Plan

| Step | File | Goal | Depends on |
|---|---|---|---|
| 1 | `01-project-setup.md` | Flask skeleton, venv, Tailwind build pipeline — a runnable, styled blank app | — |
| 2 | `02-design-system-layout.md` | Design tokens, base layout, nav, real homepage w/ two cards, error pages | 1 |
| 3 | `03-feature-compress-pdf.md` | Compress PDF, full stack | 2 |
| 4 | `04-feature-split-pdf.md` | Split PDF, full stack | 2 |
| 5 | `05-hardening-polish-qa.md` | Security hardening, UX polish, QA pass, README | 3, 4 |

Steps 3 and 4 don't depend on each other — you could do them in either order or even swap sessions if one runs into trouble.

## 9. How to Use These Files with OpenCode

1. **One file per session.** Don't paste the whole spec — just the numbered step you're working on.
2. Either paste a step file's contents directly into a fresh OpenCode session, **or** (recommended) commit all six files into the repo under `docs/spec/` and just tell the agent: *"Read `docs/spec/01-project-setup.md` and implement it."* Since OpenCode can read local files, this is more token-efficient than pasting, and doubles as living documentation.
3. Each step file recaps just enough context to stand alone — but since a fresh session has no memory of earlier sessions, tell the agent up front to inspect the existing project tree before writing anything.
4. After each step: run the app, walk through the "Definition of Done" checklist in that file, and `git commit` before starting the next session. That commit is your rollback point if a later step goes sideways, and it keeps each session's diff small — which matters more on a smaller/faster model like DeepSeek v4 Flash.
5. If any single step still feels too big for one session (context or output limits), split it further — e.g. Step 3 could become "3a: backend service + route" and "3b: template + JS" — and I'm happy to help break it down.
