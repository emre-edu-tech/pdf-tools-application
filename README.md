# PDF Toolkit

A Flask-based PDF tools application — compress, split, and more, all running locally.

## Setup

Requires **Python 3.10+** and **Node.js**.

### 1. Create and activate a virtual environment

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**

```powershell
python -m venv venv
venv\Scripts\activate
```

**For deactivating virtual environment** just run the command below:

```bash
deactivate
```

```powershell
deactivate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Node dependencies

```bash
npm install
```

### 4. Build Tailwind CSS

One-off build:

```bash
npm run build:css
```

Watch mode during development:

```bash
npm run watch:css
```

### 5. Configure environment variables

```bash
cp .env.example .env
```

`.env.example` contains:

```
SECRET_KEY=change-me
MAX_CONTENT_LENGTH=26214400
FLASK_DEBUG=1
```

* `FLASK_DEBUG=1` is **local-dev only** — do not set it in production (`wsgi.py` is used via Passenger). Debug mode enables auto-reload, verbose tracebacks, and the Werkzeug interactive debugger (arbitrary code execution if exposed). In production use `FLASK_DEBUG=0` or unset it.
* Generate a secure `SECRET_KEY` — Flask uses it to HMAC-sign session cookies, `flash` messages, and CSRF tokens; a weak/predictable key allows session forgery:

  **macOS / Linux:**

  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  # alternative: openssl rand -hex 32
  ```

  **Windows (PowerShell):**

  ```powershell
  python -c "import secrets; print(secrets.token_hex(32))"
  # alternative URL-safe: python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

  Copy the 64-hex-char output (32 bytes / 256-bit) into `.env`:

  ```
  SECRET_KEY=<paste output>
  ```

  Keep different keys per environment and never commit `.env` (it is in `.gitignore`). The placeholder `change-me` and the fallback `dev-secret-key-change-me` in `app/config.py` are dev-only.

### 6. Install Ghostscript (system binary — required for Compress PDF)

PDF compression shells out to the **Ghostscript** command-line binary via `subprocess`. It is **not** a pip package and must be installed separately on every machine that runs the app (dev and production). Tested with **Ghostscript 10.07.1**.

**Windows (local dev):**

Download the official installer at [ghostscript.com](https://ghostscript.com/) ("Ghostscript AGPL Release"). It installs a console executable named **`gswin64c.exe`** (64-bit) or `gswin32c.exe` (32-bit) — not `gs.exe`. Ensure the install directory's `bin` folder is on system `PATH` and verify:

```powershell
gswin64c --version
```

**macOS:**

```bash
brew install ghostscript
gs --version
```

**Linux (Ubuntu/Debian — matches the production server):**

```bash
sudo apt-get update
sudo apt-get install ghostscript
gs --version
```

**Environment override:**

If Ghostscript is installed but not on `PATH` (e.g. under Phusion Passenger on Plesk, where `shutil.which("gs")` may fail even though `gs --version` works over SSH), set an explicit absolute path:

```
GHOSTSCRIPT_BINARY=/usr/bin/gs
```

Add it to `.env` or the server's environment. The app checks `GHOSTSCRIPT_BINARY` first before auto-detecting `gswin64c`/`gswin32c` (Windows) or `gs` (macOS/Linux). Find the correct path on Linux with `which gs` over SSH.

> No `requirements.txt` entry is needed for Ghostscript — it's a system binary, not a pip package.

### 7. Run the application (For local dev environment - for production check [Deployment](#8-deployment))

```bash
python app.py
```

Or with Flask CLI:

```bash
flask run
```

Visit [http://127.0.0.1:5000/](http://127.0.0.1:5000/) to confirm the homepage renders.

### 8. Deployment
Running Flask applications on Plesk server with Phusion Passenger server, Nginx `proxy mode` must be disabled and the `additional Nginx directives` must be entered:

```text
passenger_enabled on;
passenger_app_type wsgi;
passenger_startup_file wsgi.py;
passenger_app_root /var/www/vhosts/example.com/httpdocs;
passenger_python /var/www/vhosts/example.com/httpdocs/venv/bin/python;
```

### 9. Application Update
If you make changes to your application and you are using Git for deployment, you can create the `tmp/restart.txt` file first (you can do it on local and push it to remote repo but you won't need to use it on local.):

run the following Git command
```bash
git pull
```

Then restart the application like this below:

```bash
touch tmp/restart.txt
```

