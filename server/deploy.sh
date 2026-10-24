#!/usr/bin/env bash
set -euo pipefail || set -eu

### ====== Config (edit these) ======
PROJECT_ID="${PROJECT_ID:-spiritual-storm-469704-n2}"
REGION="${REGION:-us-west1}"                  # e.g. us-west1
# V5's own service. fastapi-ws is the live V4 site's backend (portfolio-ws.art3m1s.me): deploying
# this code there needs SHARED_SERVICE_OK=1, see the guard below.
SERVICE_NAME="${SERVICE_NAME:-fastapi-ws-v5}" # Cloud Run service name
MAX_INSTANCES="${MAX_INSTANCES:-10}"          # cap autoscaling so costs don't spike
CONCURRENCY="${CONCURRENCY:-200}"             # WS are long-lived; raise only if your app can handle it
TIMEOUT="${TIMEOUT:-3600}"                    # seconds; Cloud Run supports up to 60m for WS
KEEP_WARM="${KEEP_WARM:-0}"                   # 1 = keep 1 warm instance (no cold start), 0 = scale to zero
ALLOW_UNAUTH="${ALLOW_UNAUTH:-1}"             # 1 = public URL
KEY_FILE="${KEY_FILE:-./gcloud.json}"         # your SA key path (optional if using personal account)
FIRETRACE="${FIRETRACE:-auto}"                # auto = mount FIRETRACE_API_KEY if the secret exists; off = never
PUSHER="${PUSHER:-auto}"                      # auto = mount PUSHER_SECRET if the secret exists; off = never
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-}"        # run as this account (fastapi-ws runs as deploy-sa@...); empty = keep/gcloud default
NO_TRAFFIC="${NO_TRAFFIC:-0}"                 # 1 = new revision gets no traffic (existing services only); test it at its tag URL
TAG="${TAG:-}"                                # revision tag, e.g. v5 -> https://v5---<service>-<hash>.run.app
CUSTOM_DOMAIN="${CUSTOM_DOMAIN:-}"            # map this domain to the service if it has no mapping yet; empty = no mapping
SHARED_SERVICE_OK="${SHARED_SERVICE_OK:-0}"   # 1 = yes, deploy to fastapi-ws, the live site's backend
### =================================

# fastapi-ws serves the live site (art3m1s.me, V4) through portfolio-ws.art3m1s.me. This repo's
# server keeps that site's classic persona as the default, but a deploy there replaces what the live
# site talks to, so it must be asked for by name. Prefer NO_TRAFFIC=1 TAG=... there, and keep the
# previous revision to roll back to:
#   gcloud run services update-traffic fastapi-ws --to-revisions <previous-revision>=100
if [[ "$SERVICE_NAME" == "fastapi-ws" && "$SHARED_SERVICE_OK" != "1" ]]; then
  echo "✗ SERVICE_NAME=fastapi-ws is the live V4 site's backend." >&2
  echo "  Deploy V5 to its own service (the default, fastapi-ws-v5), or re-run with SHARED_SERVICE_OK=1." >&2
  exit 1
fi

# Check if service account key exists, otherwise use personal account
# Fallback to parent directory if not found in current
if [[ ! -f "$KEY_FILE" && -f "../$(basename "$KEY_FILE")" ]]; then
  KEY_FILE="../$(basename "$KEY_FILE")"
fi

if [[ -f "$KEY_FILE" ]]; then
  echo "▶ Authenticating with service account key: $KEY_FILE"
  gcloud auth activate-service-account --key-file="$KEY_FILE"
else
  echo "▶ Using existing gcloud authentication (personal account)"
  echo "  (Run 'gcloud auth login' if not authenticated)"
fi

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)')"
echo "Using account: $ACTIVE_ACCOUNT"

echo "▶ Setting project & region…"
gcloud --quiet config set project "$PROJECT_ID" >/dev/null
gcloud --quiet config set run/region "$REGION" >/dev/null

echo "▶ Enabling APIs (Run, Build, Artifact Registry)…"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project "$PROJECT_ID" \
  || echo "Skipping API enable (no permission or already enabled)."

# Choose min instances based on KEEP_WARM
if [[ "$KEEP_WARM" == "1" ]]; then
  MIN_INSTANCES=1
else
  MIN_INSTANCES=0
fi

# Auth flag
if [[ "$ALLOW_UNAUTH" == "1" ]]; then
  AUTH_FLAG="--allow-unauthenticated"
else
  AUTH_FLAG="--no-allow-unauthenticated"
fi

SECRETS="OPENAI_API_KEY=OPENAI_API_KEY:latest,\
RETELL_API_KEY=RETELL_API_KEY:latest,\
PINECONE_API_KEY=PINECONE_API_KEY:latest,\
OBFUSCATED_WS_PATH=OBFUSCATED_WS_PATH:latest"

# FireTrace (tracing.art3m1s.me) is optional. The key mounted here is the
# production one for this service: FireTrace stamps the environment from the
# key, so production must never share a key with local dev. It is mounted only
# when the secret exists, so a project that never created it still deploys.
#
# The probe reads the secret (to /dev/null) because that needs only
# secretAccessor, the role this repo's accounts are documented to hold;
# `gcloud secrets describe` needs more and fails for them. Only NOT_FOUND means
# "no secret". Any other failure stops the deploy: --set-secrets replaces the
# whole set, so guessing would silently strip tracing from production.
if [[ "$FIRETRACE" == "off" ]]; then
  echo "▶ FIRETRACE=off; deploying without tracing."
elif probe="$(gcloud secrets versions access latest --secret=FIRETRACE_API_KEY --project "$PROJECT_ID" 2>&1 >/dev/null)"; then
  SECRETS="${SECRETS},FIRETRACE_API_KEY=FIRETRACE_API_KEY:latest"
  echo "▶ FIRETRACE_API_KEY found in Secret Manager; runs will be traced."
elif [[ "$probe" == *NOT_FOUND* ]]; then
  echo "▶ No FIRETRACE_API_KEY secret in Secret Manager; deploying without tracing."
else
  echo "✗ Could not read FIRETRACE_API_KEY from Secret Manager:" >&2
  echo "  $probe" >&2
  echo "  Not deploying: that would silently remove tracing from production." >&2
  echo "  Fix the account's access, or re-run with FIRETRACE=off to deploy without it." >&2
  exit 1
fi

# Pusher (voice_events.py) carries a voice call's page moves and captions to
# the browser, since Retell's v3 web calls no longer do. Without it calls still
# work, but the page doesn't follow along. Probed the same way as FireTrace,
# for the same reason: --set-secrets replaces the whole set. Unlike FireTrace,
# a missing secret stops the deploy: the site's main feature depends on it.
if [[ "$PUSHER" == "off" ]]; then
  echo "▶ PUSHER=off; voice calls won't move the page or show captions."
elif probe="$(gcloud secrets versions access latest --secret=PUSHER_SECRET --project "$PROJECT_ID" 2>&1 >/dev/null)"; then
  SECRETS="${SECRETS},PUSHER_SECRET=PUSHER_SECRET:latest"
  echo "▶ PUSHER_SECRET found in Secret Manager; voice calls will move the page."
elif [[ "$probe" == *NOT_FOUND* ]]; then
  echo "✗ No PUSHER_SECRET secret in Secret Manager." >&2
  echo "  Without it voice calls won't move the page or show captions." >&2
  echo "  Create it (see README, \"Add a new secret\"), or re-run with PUSHER=off." >&2
  exit 1
else
  echo "✗ Could not read PUSHER_SECRET from Secret Manager:" >&2
  echo "  $probe" >&2
  echo "  Not deploying: that would silently stop voice calls moving the page." >&2
  echo "  Fix the account's access, or re-run with PUSHER=off to deploy without it." >&2
  exit 1
fi

EXTRA_FLAGS=()
if [[ -n "$SERVICE_ACCOUNT" ]]; then
  EXTRA_FLAGS+=(--service-account "$SERVICE_ACCOUNT")
fi
if [[ "$NO_TRAFFIC" == "1" ]]; then
  EXTRA_FLAGS+=(--no-traffic)
fi
if [[ -n "$TAG" ]]; then
  EXTRA_FLAGS+=(--tag "$TAG")
fi

echo "▶ Deploying $SERVICE_NAME to Cloud Run (build from source)…"
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --concurrency "$CONCURRENCY" \
  --min-instances "$MIN_INSTANCES" \
  --max-instances "$MAX_INSTANCES" \
  --timeout "${TIMEOUT}s" \
  --execution-environment gen2 \
  --cpu-boost \
  --clear-env-vars \
  --set-secrets "$SECRETS" \
  ${EXTRA_FLAGS[@]+"${EXTRA_FLAGS[@]}"} \
  $AUTH_FLAG

echo "✅ Deployed. Default URL:"
gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format='value(status.url)'

# The live site's backend host, portfolio-ws.art3m1s.me, is mapped to fastapi-ws and is also
# hardcoded in the frontend (client/src/lib/backend.ts PROD_API_URL, overridable with
# NEXT_PUBLIC_API_URL) and in the Retell agent's llm_websocket_url. Change all three together: the
# frontend's warm-up ping never reads its response, so a stale host there fails silently.
# A domain that is already mapped is left alone, whichever service it points at.
if [[ -z "$CUSTOM_DOMAIN" ]]; then
  echo "▶ No CUSTOM_DOMAIN; the service answers on its run.app URL above."
  exit 0
fi

MAPPED_TO="$(gcloud beta run domain-mappings describe --domain "$CUSTOM_DOMAIN" --region "$REGION" --format='value(spec.routeName)' 2>/dev/null || true)"
if [[ -n "$MAPPED_TO" ]]; then
  echo "▶ $CUSTOM_DOMAIN is already mapped to $MAPPED_TO; left as it is."
else
  echo "▶ Creating domain mapping for ${CUSTOM_DOMAIN}…"
  gcloud beta run domain-mappings create --service "$SERVICE_NAME" \
    --domain "$CUSTOM_DOMAIN" \
    --region "$REGION"
  echo "✅ Service is mapped to: https://$CUSTOM_DOMAIN"
fi
