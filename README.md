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

Edit `.env` and set a secure `SECRET_KEY` for production.

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