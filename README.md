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

### 6. Run the application (For local dev environment - for production check [Deployment](#7-deployment))

```bash
python app.py
```

Or with Flask CLI:

```bash
flask run
```

Visit [http://127.0.0.1:5000/](http://127.0.0.1:5000/) to confirm the homepage renders.

### 7. Deployment
Running Flask applications on Plesk server with Phusion Passenger server, Nginx `proxy mode` must be disabled and the `additional Nginx directives` must be entered:

```text
passenger_enabled on;
passenger_app_type wsgi;
passenger_startup_file wsgi.py;
passenger_app_root /var/www/vhosts/example.com/httpdocs;
passenger_python /var/www/vhosts/example.com/httpdocs/venv/bin/python;
```

### 8. Application Update
If you make changes to your application and you are using Git for deployment, you can create the `tmp/restart.txt` file first (you can do it on local and push it to remote repo but you won't need to use it on local.):

```bash
touch tmp/restart.txt
```

run the following Git command
```bash
git pull
```