# Pinecone Documentation

AI agent documentation for the RAG (Retrieval Augmented Generation) system.

## Overview

This is a vector database system using Pinecone for semantic search over Bill's projects. The LLM uses this to answer questions about projects without hardcoding all details in the system prompt.

## Architecture

```
data.json → load_data.py → OpenAI Embeddings → Pinecone
                                                  ↓
LLM Query → project_search.py → Pinecone Query → Results
```

## Index Configuration

| Setting | Value |
|---------|-------|
| Index Name | `portfolio` |
| Embedding Model | `text-embedding-3-large` |
| Dimensions | 3072 |
| Metric | Cosine similarity |

## Files

```
pinecone/
├── data.json              # Source project data
├── load_data.py           # Embedding generation & upload
├── test_load_data.py      # Integration tests
├── parsed_json_list.json  # Alternative data format
└── rewrite.py             # Data transformation utilities

server/
└── project_search.py      # Runtime search functions
```

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `PINECONE_API_KEY` | Yes | Pinecone authentication |
| `OPENAI_API_KEY` | Yes | Embedding generation |

## Quick Start

### 1. Add/Edit Project Data

Edit `data.json`:
```json
{
  "id": "project-slug",
  "name": "Project Name",
  "summary": "Brief description...",
  "details": "Full details...",
  "github": "https://github.com/...",
  "demo": "https://youtube.com/..."
}
```

### 2. Upload to Pinecone

```bash
cd pinecone
python load_data.py
```

### 3. Test Search

```bash
python test_load_data.py
```

## Documentation Index

### Data
- [data/schema.md](data/schema.md) - data.json structure
- [data/pipeline.md](data/pipeline.md) - Embedding and upload workflow

### Search
- [search/functions.md](search/functions.md) - Search function reference
- [search/testing.md](search/testing.md) - Testing and debugging

## Related Documentation

- [../server/docs/tools/search.md](../../server/docs/tools/search.md) - LLM search tools
- [../server/docs/README.md](../../server/docs/README.md) - Server documentation
- [../client/docs/README.md](../../client/docs/README.md) - Frontend documentation
