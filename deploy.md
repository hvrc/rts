# RTS — Deployment Guide

How the RTS app is deployed to Google Cloud, and how to do it again repeatably.

- **Project:** `rts0-462101` (App Engine, region `us-east1`)
- **Live site:** https://rts0-462101.ue.r.appspot.com/
- **Live backend:** https://backend-dot-rts0-462101.ue.r.appspot.com/

## Architecture

The app runs as two App Engine **services** in one project:

| Service   | Runtime      | Source        | Serves                                                        |
|-----------|--------------|---------------|--------------------------------------------------------------|
| `default` | nodejs20     | `frontend/`   | the built Vite SPA (`dist/`) — the main site                 |
| `backend` | python312    | `backend/`    | the Flask API (`/echo`, `/reset`) — the Claude game brain    |

> A third service, `frontend` (nodejs22), is an old/unused deploy target. Ignore it.

The frontend calls the backend at the hardcoded prod URL in
`frontend/src/components/chat.tsx` (`import.meta.env.PROD` branch). The backend
holds the `ANTHROPIC_API_KEY` — never shipped in code; it is pulled from
**Secret Manager** at startup (see below).

## Prerequisites (one-time per machine)

```bash
# 1. Install the Google Cloud SDK
brew install --cask google-cloud-sdk

# 2. Log in (opens a browser; you approve)
gcloud auth login

# 3. Point at the project
gcloud config set project rts0-462101
```

Verify access:

```bash
gcloud app describe --format="value(id,locationId,servingStatus)"
# -> rts0-462101   us-east1   SERVING
```

## Secret Manager (one-time setup)

The backend reads `ANTHROPIC_API_KEY` from Secret Manager in production. This was
set up once and normally does not need to be repeated.

```bash
# Enable the API
gcloud services enable secretmanager.googleapis.com

# Create the secret
gcloud secrets create anthropic-api-key --replication-policy=automatic

# Add the key value as a version (piped from backend/.env so it never prints)
grep '^ANTHROPIC_API_KEY=' backend/.env | cut -d= -f2- | tr -d '\n\r' \
  | gcloud secrets versions add anthropic-api-key --data-file=-

# Let the App Engine service account read it
gcloud secrets add-iam-policy-binding anthropic-api-key \
  --member="serviceAccount:rts0-462101@appspot.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**Rotating the key later:** add a new version, then redeploy the backend (or just
restart instances). `versions/latest` is resolved at startup.

```bash
printf '%s' "sk-ant-NEW-KEY" | gcloud secrets versions add anthropic-api-key --data-file=-
```

How the code consumes it — in `backend/server.py`, right after `load_dotenv()`:

```python
if not os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("GOOGLE_CLOUD_PROJECT"):
    from google.cloud import secretmanager
    _project = os.environ["GOOGLE_CLOUD_PROJECT"]           # auto-set on App Engine
    _sm = secretmanager.SecretManagerServiceClient()
    _name = f"projects/{_project}/secrets/anthropic-api-key/versions/latest"
    os.environ["ANTHROPIC_API_KEY"] = _sm.access_secret_version(name=_name).payload.data.decode("utf-8")
```

`GOOGLE_CLOUD_PROJECT` is only present on App Engine, so **local dev skips this block
entirely** and uses `backend/.env`.

## Config files

These are **gitignored** (`*.yaml` is in `.gitignore`), so they live only on disk.
If they go missing, recreate them from the versions below.

### `backend/app.yaml`

```yaml
runtime: python312
service: backend
entrypoint: gunicorn -b :$PORT server:app

instance_class: F1

automatic_scaling:
  max_instances: 2

env_variables:
  PYTHONUNBUFFERED: '1'
  # ANTHROPIC_API_KEY is fetched from Secret Manager at startup (see server.py).

handlers:
- url: /.*
  script: auto
  secure: optional
```

### `backend/.gcloudignore`

Keeps `venv/`, `.env`, and git cruft out of the upload:

```
.gcloudignore
.git
.gitignore
venv/
env/
.venv/
__pycache__/
*.py[cod]
.env
.env.*
*.log
README.md
```

### `frontend/app.yaml` (for the `default` service)

```yaml
runtime: nodejs20
service: default

env_variables:
  VITE_API_URL: https://backend-dot-rts0-462101.ue.r.appspot.com

handlers:
- url: /(.*\.(js|css|png|jpg|json))$
  static_files: dist/\1
  upload: dist/.*\.(js|css|png|jpg|json)$
  secure: always
- url: /.*
  static_files: dist/index.html
  upload: dist/index.html
  secure: always
```

## Deploy the backend

Standard, safe procedure — deploy without traffic, smoke-test, then flip traffic.

```bash
cd backend

# 1. Deploy a new version WITHOUT touching live traffic
#    Pick a fresh version name each time (e.g. anthropic-2, anthropic-3, ...).
gcloud app deploy app.yaml --no-promote --version=anthropic-2

# 2. Smoke-test the new version on its private URL (no traffic yet).
#    This proves Secret Manager + a real Claude call work in prod.
BASE="https://anthropic-2-dot-backend-dot-rts0-462101.ue.r.appspot.com"
curl -s "$BASE/"                                                            # -> welcome to the rts brain!
curl -s -X POST "$BASE/echo" -H "Content-Type: application/json" \
  -d '{"message":"apple"}'                                                  # -> {"response": "...", "response_code":"OK", ...}

# 3. If good, migrate 100% of traffic to it
gcloud app services set-traffic backend --splits anthropic-2=1
```

Confirm which version serves traffic:

```bash
gcloud app versions list --service=backend \
  --format="table(version.id, traffic_split, version.createTime.date('%Y-%m-%d'))" \
  --sort-by="~version.createTime"
```

## Deploy the frontend (`default` service)

Only needed when the frontend changes. It ships a static build.

```bash
cd frontend
npm ci
npm run build                    # produces dist/
gcloud app deploy app.yaml       # deploys to the 'default' service
```

> The prod backend URL is hardcoded in `frontend/src/components/chat.tsx`
> (`import.meta.env.PROD` branch), so it does not depend on `VITE_API_URL` at runtime.

## Rollback

Traffic migration is instant and reversible — just point traffic at a previous version:

```bash
# List versions to find a known-good one
gcloud app versions list --service=backend

# Restore it (example: the previous WordNet backend)
gcloud app services set-traffic backend --splits 20250804t174307=1
```

## Cleanup (optional)

App Engine keeps every deployed version (they cost nothing while receiving no
traffic, but clutter up). Delete old ones you no longer need:

```bash
gcloud app versions delete VERSION_ID --service=backend
```

## Run locally (for reference)

```bash
# Backend — port 5001 (macOS AirPlay usually squats on 5000)
cd backend
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
# put your key in backend/.env:  ANTHROPIC_API_KEY=sk-ant-...
PORT=5001 ./venv/bin/python server.py

# Frontend — Vite dev server on :5173, talks to localhost:5001
cd frontend && npm install && npm run dev
```
