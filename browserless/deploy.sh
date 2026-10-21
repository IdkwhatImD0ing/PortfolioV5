#!/usr/bin/env bash
set -euo pipefail || set -eu

### ====== Config ======
PROJECT_ID="${PROJECT_ID:-spiritual-storm-469704-n2}"
REGION="${REGION:-us-west1}"
SERVICE_NAME="${SERVICE_NAME:-browserless-chromium}"
REMOTE_REPOSITORY="${REMOTE_REPOSITORY:-ghcr-remote}"
REMOTE_DOCKER_REPO="${REMOTE_DOCKER_REPO:-https://ghcr.io}"
UPSTREAM_IMAGE="${UPSTREAM_IMAGE:-browserless/chromium:latest}"
IMAGE="${IMAGE:-${REGION}-docker.pkg.dev/${PROJECT_ID}/${REMOTE_REPOSITORY}/${UPSTREAM_IMAGE}}"
PORT="${PORT:-3000}"
MEMORY="${MEMORY:-2Gi}"
CPU="${CPU:-2}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"
MAX_INSTANCES="${MAX_INSTANCES:-2}"
REQUEST_CONCURRENCY="${REQUEST_CONCURRENCY:-10}"
CONCURRENT="${CONCURRENT:-5}"
QUEUED="${QUEUED:-10}"
TIMEOUT="${TIMEOUT:-300000}"
TOKEN_SECRET_NAME="${TOKEN_SECRET_NAME:-browserless-token}"
ALLOW_UNAUTH="${ALLOW_UNAUTH:-1}"
KEY_FILE="${KEY_FILE:-./gcloud.json}"
### ====================

if [[ ! -f "$KEY_FILE" && -f "../$(basename "$KEY_FILE")" ]]; then
  KEY_FILE="../$(basename "$KEY_FILE")"
fi

if [[ -f "$KEY_FILE" ]]; then
  echo "Authenticating with service account key: $KEY_FILE"
  gcloud auth activate-service-account --key-file="$KEY_FILE"
else
  echo "Using existing gcloud authentication."
  echo "Run 'gcloud auth login' if no account is active."
fi

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)')"
echo "Using account: $ACTIVE_ACCOUNT"

echo "Setting project and region..."
gcloud --quiet config set project "$PROJECT_ID" >/dev/null
gcloud --quiet config set run/region "$REGION" >/dev/null

echo "Enabling required APIs..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com --project "$PROJECT_ID" \
  || echo "Skipping API enable; it may already be enabled or this account may not have permission."

if ! gcloud artifacts repositories describe "$REMOTE_REPOSITORY" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Creating Artifact Registry remote repository for $REMOTE_DOCKER_REPO..."
  gcloud artifacts repositories create "$REMOTE_REPOSITORY" \
    --repository-format=docker \
    --mode=remote-repository \
    --remote-repo-config-desc="GitHub Container Registry" \
    --remote-docker-repo="$REMOTE_DOCKER_REPO" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --description="Remote cache for Browserless images from GitHub Container Registry"
fi

if ! gcloud secrets describe "$TOKEN_SECRET_NAME" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Missing Secret Manager secret: $TOKEN_SECRET_NAME"
  echo "Create it before deploying:"
  echo "  printf '%s' 'replace-with-a-strong-token' | gcloud secrets create $TOKEN_SECRET_NAME --data-file=- --project $PROJECT_ID"
  exit 1
fi

if [[ "$ALLOW_UNAUTH" == "1" ]]; then
  AUTH_FLAG="--allow-unauthenticated"
else
  AUTH_FLAG="--no-allow-unauthenticated"
fi

echo "Deploying $SERVICE_NAME to Cloud Run from $IMAGE..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --region "$REGION" \
  --port "$PORT" \
  --memory "$MEMORY" \
  --cpu "$CPU" \
  --concurrency "$REQUEST_CONCURRENCY" \
  --min-instances "$MIN_INSTANCES" \
  --max-instances "$MAX_INSTANCES" \
  --set-env-vars "CONCURRENT=$CONCURRENT,QUEUED=$QUEUED,TIMEOUT=$TIMEOUT" \
  --set-secrets "TOKEN=$TOKEN_SECRET_NAME:latest" \
  --execution-environment gen2 \
  $AUTH_FLAG

SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format='value(status.url)')"

echo "Deployed. Default URL:"
echo "$SERVICE_URL"
echo
echo "Verify with:"
echo "  curl -X POST \"${SERVICE_URL}/content?token=\$BROWSERLESS_TOKEN\" -H \"Content-Type: application/json\" -d '{\"url\":\"https://example.com/\"}'"
