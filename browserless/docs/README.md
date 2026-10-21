# Browserless Cloud Run Deployment

This module deploys Browserless Open Source as a separate Google Cloud Run service for headless browser automation. It is intentionally separate from the FastAPI voice backend in `server/`.

## Overview

| Setting | Default |
|---------|---------|
| Service name | `browserless-chromium` |
| Region | `us-west1` |
| Upstream image | `ghcr.io/browserless/chromium:latest` |
| Artifact Registry remote repository | `ghcr-remote` |
| Port | `3000` |
| Min instances | `0` |
| Max instances | `2` |
| Memory | `2Gi` |
| CPU | `2` |
| Browser sessions | `CONCURRENT=5` |
| Queue length | `QUEUED=10` |
| Session timeout | `TIMEOUT=300000` |

The service is deployed with a public Cloud Run URL and Browserless token authentication. Do not expose the token through `NEXT_PUBLIC_*` variables or browser-side code.

## Local Docker

Run Chromium locally with a development token:

```bash
docker run --rm \
  -p 3000:3000 \
  -e "CONCURRENT=5" \
  -e "QUEUED=10" \
  -e "TIMEOUT=300000" \
  -e "TOKEN=local-browserless-token" \
  ghcr.io/browserless/chromium
```

Verify the local service:

```bash
curl -X POST "http://localhost:3000/content?token=local-browserless-token" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/"}'
```

## Production Secret

Create the Browserless token in Google Secret Manager before deploying:

```bash
printf '%s' 'replace-with-a-strong-token' \
  | gcloud secrets create browserless-token \
    --data-file=- \
    --project spiritual-storm-469704-n2
```

To rotate the token later:

```bash
printf '%s' 'replace-with-a-new-strong-token' \
  | gcloud secrets versions add browserless-token \
    --data-file=- \
    --project spiritual-storm-469704-n2
```

Keep the token in a local shell variable only when you need to verify the service:

```bash
export BROWSERLESS_TOKEN="replace-with-the-current-token"
```

## Deploy

Run the deploy script from this module:

```bash
cd browserless
bash deploy.sh
```

The script creates an Artifact Registry remote repository for `https://ghcr.io` if one does not already exist, then deploys the Browserless image through that repository. Cloud Run supports Artifact Registry images directly, and the remote repository caches the upstream GitHub Container Registry image.

Override defaults with environment variables when needed:

```bash
MAX_INSTANCES=1 CONCURRENT=3 QUEUED=5 bash deploy.sh
```

Useful variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `PROJECT_ID` | `spiritual-storm-469704-n2` | Google Cloud project |
| `REGION` | `us-west1` | Cloud Run region |
| `SERVICE_NAME` | `browserless-chromium` | Cloud Run service |
| `REMOTE_REPOSITORY` | `ghcr-remote` | Artifact Registry remote repository |
| `REMOTE_DOCKER_REPO` | `https://ghcr.io` | Upstream Docker registry |
| `UPSTREAM_IMAGE` | `browserless/chromium:latest` | Browserless image in the upstream registry |
| `IMAGE` | Derived Artifact Registry URL | Override the deployed image URL |
| `TOKEN_SECRET_NAME` | `browserless-token` | Secret Manager token name |
| `MIN_INSTANCES` | `0` | Scale to zero when unused |
| `MAX_INSTANCES` | `2` | Cost and scaling cap |
| `REQUEST_CONCURRENCY` | `10` | Cloud Run HTTP request concurrency |
| `CONCURRENT` | `5` | Browserless concurrent browser sessions |
| `QUEUED` | `10` | Browserless queued requests |
| `TIMEOUT` | `300000` | Browserless session timeout in milliseconds |
| `ALLOW_UNAUTH` | `1` | Public Cloud Run URL protected by Browserless token |

## Verify Production

After deployment, the script prints the Cloud Run URL. Test the content endpoint:

```bash
curl -X POST "https://<cloud-run-url>/content?token=$BROWSERLESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/"}'
```

You should receive the HTML for `example.com`.

View recent logs:

```bash
gcloud run logs read browserless-chromium --region us-west1
```

Stream logs while testing:

```bash
gcloud run logs tail browserless-chromium --region us-west1
```

## Cost Controls

- `MIN_INSTANCES=0` keeps the service scaled to zero when unused.
- `MAX_INSTANCES=2` caps autoscaling so unexpected traffic cannot fan out heavily.
- `CONCURRENT=5` limits active browser sessions inside each container.
- `QUEUED=10` limits queued work instead of letting requests pile up indefinitely.
- `TIMEOUT=300000` closes long sessions after five minutes.

Set `MAX_INSTANCES=1` for the lowest-cost production posture if one active container is enough.

## Integration Notes

Use Browserless only from trusted server-side code, such as the FastAPI backend or a private script. Keep the token in Cloud Run, Secret Manager, or local shell state. If the Next.js frontend needs a Browserless-backed feature later, add a server-side API route or backend endpoint rather than calling Browserless directly from the browser.
