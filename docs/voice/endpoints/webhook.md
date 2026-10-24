# POST /webhook

Documentation for the Retell webhook endpoint.

## File Location

`main.py` (lines 82-113)

## Purpose

Receives webhook events from Retell platform for call lifecycle events:
- `call_started` - Call has begun
- `call_ended` - Call has terminated
- `call_analyzed` - Post-call analysis complete

## Endpoint

```
POST /webhook
```

## Request

### Headers

```
Content-Type: application/json
X-Retell-Signature: <signature>
```

### Body

```json
{
  "event": "call_started" | "call_ended" | "call_analyzed",
  "data": {
    "call_id": "call_xxx",
    // ... additional event data
  }
}
```

## Response

### Success (200)

```json
{
  "received": true
}
```

### Unauthorized (401)

```json
{
  "message": "Unauthorized"
}
```

### Error (500)

```json
{
  "message": "Internal Server Error"
}
```

## Signature Verification

Retell signs all webhook requests. The server verifies signatures:

```python
valid_signature = retell.verify(
    json.dumps(post_data, separators=(",", ":"), ensure_ascii=False),
    api_key=str(os.getenv("RETELL_API_KEY")),
    signature=str(request.headers.get("X-Retell-Signature")),
)

if not valid_signature:
    return JSONResponse(status_code=401, content={"message": "Unauthorized"})
```

## Event Handling

```python
if post_data["event"] == "call_started":
    print("Call started event", post_data["data"]["call_id"])
elif post_data["event"] == "call_ended":
    print("Call ended event", post_data["data"]["call_id"])
elif post_data["event"] == "call_analyzed":
    print("Call analyzed event", post_data["data"]["call_id"])
```

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `RETELL_API_KEY` | Yes | Signature verification |

## Retell Dashboard Setup

1. Go to Retell Dashboard → Settings → Webhooks
2. Add webhook URL: `https://your-server.run.app/webhook`
3. Select events to receive

## Modifications

### Store Call Data

```python
if post_data["event"] == "call_ended":
    call_id = post_data["data"]["call_id"]
    duration = post_data["data"].get("duration")
    # Store in database
    await db.calls.insert({
        "call_id": call_id,
        "duration": duration,
        "ended_at": datetime.utcnow()
    })
```

### Send Notifications

```python
if post_data["event"] == "call_ended":
    await send_slack_notification(
        f"Call {post_data['data']['call_id']} ended"
    )
```

### Add Call Analytics

```python
if post_data["event"] == "call_analyzed":
    analysis = post_data["data"]["analysis"]
    sentiment = analysis.get("sentiment")
    topics = analysis.get("topics")
    # Process analytics
```

## Security Notes

- Always verify the `X-Retell-Signature` header
- The endpoint should only be accessible from Retell IPs in production
- Never log sensitive call data without proper redaction

## Related Files

- [websocket.md](websocket.md) - Real-time call handling
- [ping.md](ping.md) - Health check endpoint
