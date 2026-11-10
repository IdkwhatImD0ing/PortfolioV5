# Server Documentation

> Moved here from `server/docs/` on 2026-10-24, when every doc moved into `docs/`. File paths inside it are relative to `server/`.

AI agent documentation for the FastAPI backend of Bill Zhang's voice portfolio.

## Overview

This is a FastAPI server that bridges Retell's voice platform with OpenAI's LLM. It handles real-time
voice conversations, navigation tools, semantic search through Pinecone, and private soundtrack
streaming from Cloud Storage.

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.116.1 | Web framework |
| Uvicorn | 0.32.0 | ASGI server |
| OpenAI Agents | 0.2.7 | LLM integration |
| Pinecone | 7.3.0 | Vector database |
| Retell SDK | 4.40.0 | Webhook verification |
| Google Cloud Storage | 3.4.1 | Private soundtrack objects |
| Python | 3.11 | Runtime |

## Architecture

```
server/
├── main.py              # FastAPI app, endpoints, WebSocket
├── llm.py               # LLM client, tools, guardrails
├── firetrace.py         # FireTrace exporter: one trace per completed run
├── project_search.py    # Pinecone search functions
├── music.py             # Soundtrack manifest, capabilities, ranges and lyrics
├── music_manifest.json  # Internal media-object mapping and playback metadata
├── prompts.py           # System prompt and persona
├── prompts_sect.py      # The senior disciple's prompt for the sect
├── personas.py          # Picks the classic or sect persona for a call
├── model_config.py      # Which model runs the agent, the guardrail and the call summary
├── navigation.py        # Turns a display_* tool call into a navigation message
├── voice_events.py      # Publishes navigation and live captions to the call's Pusher channel
├── custom_types.py      # Pydantic type definitions
├── socket_manager.py    # WebSocket connection manager
├── Dockerfile           # Container configuration
└── deploy.sh            # Cloud Run deployment
```

## Request Flow

```
User Speech → Retell Platform → WebSocket → main.py
    → LlmClient.draft_response() → OpenAI Agents SDK
    → Tool calls → Pinecone (if search)
    → Streaming response → WebSocket → Retell → Voice

Page moves take a second path:
    display_* tool call → navigation.py → voice_events.py
    → Pusher channel voice-<uuid> → pusher-js in the browser → the page flies there
Live captions take the same Pusher channel, starting from Retell's transcript updates (main.py → voice_events.py).
```

The browser makes up the channel id, subscribes to it, and passes it to Retell in the call's `metadata.events_channel`. The server only accepts a lowercase UUID as the id.

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `RETELL_API_KEY` | Yes | - | Retell webhook verification |
| `OPENAI_API_KEY` | Yes | - | LLM and embeddings |
| `PINECONE_API_KEY` | Yes | - | Vector database |
| `OBFUSCATED_WS_PATH` | No | `ws-default` | Secret WebSocket path (value never logged; startup warns if unset) |
| `LLM_DEBUG` | No | `0` | Debug logging |
| `FIRETRACE_API_KEY` | No | - | Records every run at tracing.art3m1s.me; one key per environment |
| `MUSIC_BUCKET` | Cloud Run | - | Private soundtrack bucket |
| `MUSIC_SIGNING_SECRET` | Cloud Run | - | Signs short-lived soundtrack capabilities |
| `MUSIC_STORAGE_DIR` | Local only | - | Prepared local soundtrack directory |

## Development Commands

```bash
cd server
pip install -r requirements.txt    # Install dependencies
uvicorn main:app --reload          # Start dev server
python run_integration_tests.py    # Run tests
```

## Documentation Index

### Endpoints
- [endpoints/ping.md](endpoints/ping.md) - Health check
- [endpoints/webhook.md](endpoints/webhook.md) - Retell webhook
- [endpoints/websocket.md](endpoints/websocket.md) - WebSocket handler

### Tools
- [tools/navigation.md](tools/navigation.md) - Page navigation tools
- [tools/search.md](tools/search.md) - Project search tools

### Modules
- [modules/llm.md](modules/llm.md) - LLM client class
- [modules/guardrail.md](modules/guardrail.md) - Security guardrail
- [modules/firetrace.md](modules/firetrace.md) - FireTrace tracing exporter
- [modules/prompts.md](modules/prompts.md) - System prompt

### Deployment
- [../deploy/docker.md](../deploy/docker.md) - Docker and Cloud Run

## Related Documentation

- [../README.md](../README.md) - Index of every doc in the repo
- [pinecone/README.md](pinecone/README.md) - Vector database documentation
