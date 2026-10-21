# Docker & Deployment

Documentation for containerization and Cloud Run deployment.

## File Locations

- `Dockerfile` - Container configuration
- `deploy.sh` - Cloud Run deployment script

## Related Services

Browserless is deployed as a separate Cloud Run service from the repository-level `browserless/` module. See [../../../browserless/docs/README.md](../../../browserless/docs/README.md) for the headless browser deployment path.

## Dockerfile

```dockerfile
FROM python:3.11-slim

# Install build dependencies for pyaudio
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc build-essential libasound2-dev portaudio19-dev python3-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Build Dependencies

PyAudio requires C compilation:
- `gcc`, `build-essential` - C compiler
- `libasound2-dev` - ALSA development files
- `portaudio19-dev` - PortAudio library
- `python3-dev` - Python headers

## Local Docker Build

### Build Image

```bash
cd server
docker build -t portfolio-server .
```

### Run Container

```bash
docker run -p 8080:8080 \
  -e RETELL_API_KEY=your_key \
  -e OPENAI_API_KEY=your_key \
  -e PINECONE_API_KEY=your_key \
  -e OBFUSCATED_WS_PATH=your_path \
  portfolio-server
```

### Using .env File

```bash
docker run -p 8080:8080 --env-file .env portfolio-server
```

### Test Locally

```bash
curl http://localhost:8080/ping
# {"message": "pong"}
```

## Google Cloud Run

### Production URLs

| URL Type | Value |
|----------|-------|
| Default URL | `https://fastapi-ws-815644024160.us-west1.run.app` |
| Service Name | `fastapi-ws` |
| Region | `us-west1` |

### Prerequisites

1. Google Cloud account
2. `gcloud` CLI installed and authenticated
3. Cloud Run API enabled

### Deploy Script

`deploy.sh`:

```bash
#!/bin/bash

# Configuration
PROJECT_ID="your-project-id"
REGION="us-west1"
SERVICE_NAME="portfolio-server"

# Build and push
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Deploy
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --timeout 3600 \
  --min-instances 0 \
  --max-instances 10 \
  --concurrency 80
```

### Run Deployment

```bash
chmod +x deploy.sh
./deploy.sh
```

### Environment Variables

Set in Cloud Run console or via CLI:

```bash
gcloud run services update portfolio-server \
  --set-env-vars="RETELL_API_KEY=xxx,OPENAI_API_KEY=xxx,PINECONE_API_KEY=xxx"
```

### Custom Domain

Map a custom domain:

```bash
gcloud beta run domain-mappings create \
  --service portfolio-server \
  --domain portfolio-ws.art3m1s.me \
  --region us-west1
```

## Configuration Options

### WebSocket Timeout

Cloud Run default is 300s. For long calls:

```bash
--timeout 3600  # 60 minutes
```

### Scaling

```bash
--min-instances 0   # Scale to zero (cold starts)
--min-instances 1   # Keep warm (no cold starts, costs more)
--max-instances 10  # Maximum concurrent instances
--concurrency 80    # Requests per instance
```

### Memory & CPU

```bash
--memory 512Mi  # Memory allocation
--cpu 1         # CPU allocation
```

## Monitoring

### View Logs

```bash
gcloud run logs read portfolio-server --region us-west1
```

### Stream Logs

```bash
gcloud run logs tail portfolio-server --region us-west1
```

### Metrics

View in Cloud Console:
- Request count
- Latency
- Instance count
- Error rate

## Troubleshooting

### Cold Start Issues

If first request is slow:
1. Set `--min-instances 1` to keep warm
2. Frontend pings `/ping` on page load

### WebSocket Disconnects

If connections drop after 5 minutes:
1. Increase `--timeout` to 3600
2. Enable `auto_reconnect: true` in config

### Memory Errors

If container runs out of memory:
1. Increase `--memory 1Gi`
2. Check for memory leaks in long-running connections

### Build Failures

If PyAudio fails to build:
1. Ensure Dockerfile has all build dependencies
2. Use `python:3.11-slim` base (not alpine)

## Modifications

### Change Port

```dockerfile
ENV PORT=3000
EXPOSE 3000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
```

### Add Health Check

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s \
  CMD curl -f http://localhost:8080/ping || exit 1
```

### Multi-stage Build

```dockerfile
FROM python:3.11-slim as builder
# ... build steps

FROM python:3.11-slim
COPY --from=builder /app /app
```

## Related Files

- `requirements.txt` - Python dependencies
- `main.py` - Application entry point
- [../endpoints/ping.md](../endpoints/ping.md) - Health check endpoint
