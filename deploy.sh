#!/usr/bin/env bash
# Deploy RTS (Python Flask backend + Vite React frontend) to Google Cloud Run.
#
#   PROJECT_ID=hvrc-web REGION=us-east1 ./deploy.sh
#
# Builds happen in Cloud Build (no local Docker needed). The backend reads its
# Anthropic key from Secret Manager (mounted, never printed); the frontend has the
# backend URL baked in at build time via VITE_API_URL. Backend keeps in-memory game
# state, so it is pinned to a single instance.
#
#   SKIP_GRANT=1 ./deploy.sh   skip the one-time secret IAM grant (already done)
#   VERIFY_ONLY=1 ./deploy.sh  just check what is live right now
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-hvrc-web}"
REGION="${REGION:-us-east1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-rts-backend}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-rts-frontend}"
SECRET="${SECRET:-rts-anthropic-key}"          # secret name in this project's Secret Manager
CUSTOM_DOMAIN="${CUSTOM_DOMAIN-rts.hvrc.place}"     # frontend subdomain
BACKEND_DOMAIN="${BACKEND_DOMAIN-str.hvrc.place}"   # backend subdomain (frontend calls this)
ROOT="$(cd "$(dirname "$0")" && pwd)"

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud config set project "${PROJECT_ID}" >/dev/null

verify() {
  local burl="$1" furl="$2" fail=0
  echo "── Verifying ───────────────────────────────────────────────"
  if curl -fsS --max-time 30 "${burl}/" | grep -qi "rts brain"; then
    echo "  OK   backend is up"; else echo "  FAIL backend / did not respond"; fail=1; fi
  if curl -sS --max-time 60 -X POST "${burl}/reset" -H 'Content-Type: application/json' \
        -d '{"reverse":false}' | grep -q "response"; then
    echo "  OK   backend /reset works (Anthropic key readable)"
  else echo "  FAIL backend /reset failed — secret not readable? check the IAM grant"; fail=1; fi
  if [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "${furl}")" = "200" ]; then
    echo "  OK   frontend serves 200"; else echo "  FAIL frontend not serving"; fail=1; fi
  [ "${fail}" -eq 0 ] && echo "Verified live." || { echo "VERIFICATION FAILED"; return 1; }
}

if [ "${VERIFY_ONLY:-0}" = "1" ]; then
  BURL="$(gcloud run services describe "${BACKEND_SERVICE}" --region "${REGION}" --format='value(status.url)')"
  FURL="$(gcloud run services describe "${FRONTEND_SERVICE}" --region "${REGION}" --format='value(status.url)')"
  verify "${BURL}" "${FURL}"; exit $?
fi

gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com --project "${PROJECT_ID}" --quiet >/dev/null

# 0) One-time: let the Cloud Run runtime SA read the Anthropic secret.
#    (This is the single grant that must be approved — it is why rts waited.)
if [ "${SKIP_GRANT:-0}" != "1" ]; then
  echo "── Granting ${RUNTIME_SA} read on secret ${SECRET} ─────────"
  gcloud secrets add-iam-policy-binding "${SECRET}" --project "${PROJECT_ID}" \
    --member "serviceAccount:${RUNTIME_SA}" \
    --role roles/secretmanager.secretAccessor --quiet >/dev/null
fi

# 1) Backend — single instance (in-memory state), secret mounted, CORS via env var.
echo "── Deploying ${BACKEND_SERVICE} ────────────────────────────"
gcloud run deploy "${BACKEND_SERVICE}" \
  --source backend --region "${REGION}" --allow-unauthenticated \
  --min-instances 0 --max-instances 1 --cpu 1 --memory 512Mi --port 8080 --timeout 120 \
  --set-secrets "ANTHROPIC_API_KEY=${SECRET}:latest" \
  --set-env-vars "CORS_ORIGINS=https://${CUSTOM_DOMAIN}" \
  --quiet
BURL="$(gcloud run services describe "${BACKEND_SERVICE}" --region "${REGION}" --format='value(status.url)')"
echo "Backend URL: ${BURL}"

# 2) Frontend — static SPA; backend URL baked in at build time. Points at the backend's
#    custom subdomain (str.hvrc.place) so it survives the backend being redeployed.
FRONTEND_API="https://${BACKEND_DOMAIN:-$BURL}"
echo "── Deploying ${FRONTEND_SERVICE} (API=${FRONTEND_API}) ──────"
gcloud run deploy "${FRONTEND_SERVICE}" \
  --source frontend --region "${REGION}" --allow-unauthenticated \
  --min-instances 0 --max-instances 2 --cpu 1 --memory 256Mi --port 8080 \
  --build-env-vars "VITE_API_URL=${FRONTEND_API}" \
  --quiet 2>/dev/null || \
gcloud run deploy "${FRONTEND_SERVICE}" \
  --source frontend --region "${REGION}" --allow-unauthenticated \
  --min-instances 0 --max-instances 2 --cpu 1 --memory 256Mi --port 8080 --quiet
FURL="$(gcloud run services describe "${FRONTEND_SERVICE}" --region "${REGION}" --format='value(status.url)')"
echo "Frontend URL: ${FURL}"

# 3) Widen backend CORS to allow the frontend custom domain AND its run.app URL.
gcloud run services update "${BACKEND_SERVICE}" --region "${REGION}" \
  --update-env-vars "^@^CORS_ORIGINS=https://${CUSTOM_DOMAIN},${FURL}" --quiet >/dev/null

# 4) Ensure both subdomains are mapped (idempotent): frontend + backend.
[ -n "${CUSTOM_DOMAIN}" ] && gcloud beta run domain-mappings create --service "${FRONTEND_SERVICE}" \
    --domain "${CUSTOM_DOMAIN}" --region "${REGION}" --quiet 2>/dev/null || true
[ -n "${BACKEND_DOMAIN}" ] && gcloud beta run domain-mappings create --service "${BACKEND_SERVICE}" \
    --domain "${BACKEND_DOMAIN}" --region "${REGION}" --quiet 2>/dev/null || true

verify "${BURL}" "${FURL}"
echo "If the frontend calls the OLD backend URL, it was built before this backend existed —"
echo "just re-run: the Dockerfile now bakes VITE_API_URL=${BURL}."
