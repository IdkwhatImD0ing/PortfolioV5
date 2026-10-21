# Data Pipeline

Documentation for the embedding generation and Pinecone upload workflow.

## File Location

`pinecone/load_data.py`

## Purpose

Transforms project data from `data.json` into vector embeddings and uploads them to Pinecone.

## Pipeline Flow

```
data.json → Read JSON → Generate Embeddings → Prepare Vectors → Upsert to Pinecone
```

## Configuration

```python
INDEX_NAME = "portfolio"
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 3072
```

## Functions

### get_embedding()

Generate embedding for text using OpenAI.

```python
def get_embedding(text: str) -> List[float]:
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )
    return response.data[0].embedding
```

### prepare_vectors()

Transform project data into Pinecone vectors.

```python
def prepare_vectors(data: List[Dict]) -> List[tuple]:
    vectors = []
    
    for item in data:
        # Combine fields for embedding
        text_content = f"""
        Project: {item['name']}
        
        Summary:
        {item['summary']}
        
        Details:
        {item['details']}
        """
        
        embedding = get_embedding(text_content)
        
        metadata = {
            "id": item["id"],
            "name": item["name"],
            "summary": item["summary"],
            "details": item["details"],
        }
        
        if item.get("github"):
            metadata["github"] = item["github"]
        if item.get("demo"):
            metadata["demo"] = item["demo"]
        
        vectors.append((item["id"], embedding, metadata))
    
    return vectors
```

### main()

Execute the full pipeline.

```python
def main():
    # 1. Load data
    with open("data.json", "r") as f:
        data = json.load(f)
    
    # 2. Connect to index
    index = pc.Index(INDEX_NAME)
    
    # 3. Generate embeddings
    vectors = prepare_vectors(data)
    
    # 4. Upload to Pinecone
    index.upsert(vectors=vectors)
    
    # 5. Verify with test query
    test_query = "interview preparation AI coaching"
    results = index.query(vector=get_embedding(test_query), top_k=3)
```

## Usage

### Run Pipeline

```bash
cd pinecone
python load_data.py
```

### Expected Output

```
Loading data...
Found 25 projects to load
Connecting to Pinecone index...
Index stats before upload: {'dimension': 3072, 'total_vector_count': 25}
Generating embeddings...
Uploading 25 vectors to Pinecone...
Index stats after upload: {'dimension': 3072, 'total_vector_count': 25}

Testing retrieval with a sample query...
Top 3 results for query 'interview preparation AI coaching':

1. InterviewGPT (Score: 0.842)
   ID: interviewgpt
   Summary preview: AI-powered interview preparation...
```

## Upsert Behavior

Pinecone upsert:
- **Insert**: New vectors are added
- **Update**: Existing vectors (same ID) are replaced

This means:
- Safe to run multiple times
- Changed data will update
- Deleted projects must be manually removed

## Removing Projects

To remove a project no longer in `data.json`:

```python
index.delete(ids=["old-project-id"])
```

Or delete all and re-upload:

```python
index.delete(delete_all=True)
# Then run load_data.py
```

## Rate Limits

### OpenAI

~3000 requests/minute for embeddings. For 25 projects, this is fine. For larger datasets:

```python
import time

for item in data:
    embedding = get_embedding(text_content)
    time.sleep(0.1)  # Rate limiting
```

### Pinecone

Batch upserts for efficiency:

```python
# Current (simple)
index.upsert(vectors=vectors)

# Batched (for large datasets)
batch_size = 100
for i in range(0, len(vectors), batch_size):
    batch = vectors[i:i+batch_size]
    index.upsert(vectors=batch)
```

## Modifications

### Change Embedding Model

```python
EMBEDDING_MODEL = "text-embedding-3-small"  # Smaller, faster
EMBEDDING_DIMENSIONS = 1536  # Update dimensions
```

Note: Changing dimensions requires recreating the Pinecone index.

### Add Fields to Embedding

Include more context in the embedding:

```python
text_content = f"""
Project: {item['name']}
Tags: {', '.join(item.get('tags', []))}

Summary:
{item['summary']}
"""
```

### Add Preprocessing

Clean data before embedding:

```python
def preprocess_text(text):
    # Remove markdown
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    return text

text_content = preprocess_text(text_content)
```

## Debugging

### Check Index Stats

```python
index = pc.Index(INDEX_NAME)
print(index.describe_index_stats())
```

### Verify Single Vector

```python
fetch_result = index.fetch(ids=["dispatch-ai"])
print(fetch_result.vectors["dispatch-ai"].metadata)
```

### Test Search

```python
query = "AI hackathon project"
embedding = get_embedding(query)
results = index.query(vector=embedding, top_k=3, include_metadata=True)
for match in results.matches:
    print(f"{match.metadata['name']}: {match.score}")
```

## Related Files

- [schema.md](schema.md) - Data structure
- `test_load_data.py` - Integration tests
- `../server/project_search.py` - Runtime search
