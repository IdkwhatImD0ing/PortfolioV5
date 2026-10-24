# Data Schema

Documentation for the project data structure in `data.json`.

## File Location

`pinecone/data.json`

## Purpose

Source of truth for all project information. Used for:
- Generating vector embeddings
- Populating Pinecone metadata
- Frontend display (`/public/data.json`)

## Schema

```typescript
interface Project {
  id: string;           // Required: Unique identifier
  name: string;         // Required: Display name
  summary: string;      // Required: Brief description
  details: string;      // Required: Full description
  github?: string;      // Optional: GitHub URL
  demo?: string;        // Optional: Demo URL (YouTube/image)
}
```

## Required Fields

### id

Unique identifier used as Pinecone vector ID.

```json
"id": "dispatch-ai"
```

Rules:
- Lowercase, hyphen-separated
- No spaces or special characters
- Must be unique across all projects

### name

Display name shown in search results and UI.

```json
"name": "Dispatch AI"
```

### summary

Brief 2-3 sentence description. Returned by `search_projects()`.

```json
"summary": "Dispatch AI is an innovative, AI-powered system designed to revolutionize emergency call handling by providing empathetic and intelligent support..."
```

Guidelines:
- 2-3 sentences
- Highlight key features
- Mention awards if notable
- Keep under 500 characters for efficiency

### details

Full project description. Returned by `get_project_details()`.

```json
"details": "Inspiration\nImagine: A major earthquake hits...\n\nWhat it does\nDispatchAI reimagines emergency response..."
```

Typical sections:
- Inspiration / Problem
- What it does
- How we built it
- Challenges
- Accomplishments
- What we learned
- What's next

## Optional Fields

### github

Repository URL. Displayed on project page.

```json
"github": "https://github.com/IdkwhatImD0ing/DispatchAI"
```

### demo

Demo video or image URL.

```json
"demo": "https://youtu.be/hdpdgxrilQM"
```

Supported formats:
- YouTube: `https://youtu.be/xxx` or `https://youtube.com/watch?v=xxx`
- Image: Direct URL to image file

## Example Entry

```json
{
  "id": "dispatch-ai",
  "name": "Dispatch AI",
  "summary": "Dispatch AI is an innovative, AI-powered system designed to revolutionize emergency call handling by providing empathetic and intelligent support. The platform centralizes 911 calls, categorizing them by severity and extracting crucial details such as location, time, and caller emotions to recommend appropriate actions.",
  "details": "Inspiration\nImagine: A major earthquake hits. Thousands call 911 simultaneously...\n\nWhat it does\nDispatchAI reimagines emergency response with an empathetic AI-powered system...\n\nHow we built it\nWe developed DispatchAI using a comprehensive tech stack:\n- Frontend: Next.js, TailwindCSS, Leaflet\n- Backend: Python, Twilio, Hume\n...\n\nAccomplishments\n- Winner of UC Berkeley AI Hackathon 2024 Grand Prize\n- $25,000 Berkeley SkyDeck Fund investment",
  "github": "https://github.com/IdkwhatImD0ing/DispatchAI",
  "demo": "https://youtu.be/hdpdgxrilQM"
}
```

## Embedding Text

The embedding is generated from combined fields:

```python
text_content = f"""
Project: {item['name']}

Summary:
{item['summary']}

Details:
{item['details']}
"""
```

This ensures semantic search can match on any part of the project.

## Pinecone Metadata

All fields are stored as Pinecone metadata:

```python
metadata = {
    "id": project_id,
    "name": item["name"],
    "summary": item["summary"],
    "details": item["details"],
}

if item.get("github"):
    metadata["github"] = item["github"]
if item.get("demo"):
    metadata["demo"] = item["demo"]
```

## Modifications

### Add New Field

1. Update `data.json`:
```json
{
  "id": "project",
  "tags": ["AI", "Web", "Hackathon"]
}
```

2. Update `load_data.py`:
```python
if item.get("tags"):
    metadata["tags"] = item["tags"]
```

3. Update `project_search.py` if needed for retrieval.

### Change Summary Length

For longer summaries, consider:
- Pinecone metadata size limits (~40KB per vector)
- Token efficiency when returned to LLM
- Search relevance (longer = more to match)

## Flagship Projects

Always keep these projects:

| ID | Name | Why |
|----|------|-----|
| `dispatch-ai` | Dispatch AI | Berkeley Grand Prize |
| `teachme-3p7bw1` | AdaptEd | LA Hacks Google Challenge |
| `talktuahbank` | TalkTuahBank | HackUTD General + Goldman |

These are referenced in the system prompt for default recommendations.

## Related Files

- [pipeline.md](pipeline.md) - How data is uploaded
- `load_data.py` - Embedding generation
- `/public/data.json` - Frontend copy
