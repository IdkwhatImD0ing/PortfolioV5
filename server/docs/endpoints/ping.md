# GET /ping

Documentation for the health check endpoint.

## File Location

`main.py` (line 77-79)

## Purpose

Simple health check endpoint used to:
- Verify the server is running
- Wake up Cloud Run instances (cold start)
- Monitor uptime

## Endpoint

```
GET /ping
```

## Response

```json
{
  "message": "pong"
}
```

## Implementation

```python
@app.get("/ping")
async def ping():
    return {"message": "pong"}
```

## Usage

### Health Check

```bash
curl https://your-server.run.app/ping
# {"message": "pong"}
```

### Frontend Warm-up

The frontend calls this on page load to wake up Cloud Run:

```typescript
// client/src/app/page.tsx
useEffect(() => {
  fetch('https://fastapi-ws-815644024160.us-west1.run.app/ping');
}, []);
```

## Cloud Run Cold Start

Cloud Run instances scale to zero when idle. The first request after idle triggers a cold start (~2-5 seconds). Calling `/ping` on page load warms up the instance before the user starts a voice call.

## Modifications

### Add Health Details

```python
@app.get("/ping")
async def ping():
    return {
        "message": "pong",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }
```

### Add Dependency Checks

```python
@app.get("/health")
async def health():
    checks = {
        "server": "ok",
        "openai": check_openai_connection(),
        "pinecone": check_pinecone_connection(),
    }
    status = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
```

## Related Files

- [websocket.md](websocket.md) - Main WebSocket endpoint
- [webhook.md](webhook.md) - Retell webhook endpoint
