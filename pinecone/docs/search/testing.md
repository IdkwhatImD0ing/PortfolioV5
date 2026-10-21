# Testing & Debugging

Documentation for testing the Pinecone integration.

## File Location

`pinecone/test_load_data.py`

## Purpose

Integration tests for:
- API connections (OpenAI, Pinecone)
- Data loading workflow
- Search functionality
- Vector operations

## Test Functions

### test_connection()

Verify API connections are working.

```python
def test_connection():
    # Test OpenAI
    response = openai_client.embeddings.create(
        model="text-embedding-3-large",
        input="test connection"
    )
    print("✓ OpenAI API connection successful")
    print(f"  Embedding dimensions: {len(response.data[0].embedding)}")
    
    # Test Pinecone
    index = pc.Index(INDEX_NAME)
    stats = index.describe_index_stats()
    print("✓ Pinecone connection successful")
    print(f"  Index stats: {stats}")
```

### test_load_and_query()

Test the full load → query workflow.

```python
def test_load_and_query():
    # Run load_data
    import load_data
    load_data.main()
    
    # Test queries
    test_queries = [
        "AI and machine learning projects",
        "web development full stack",
        "hackathon winners",
    ]
    
    for query in test_queries:
        embedding = load_data.get_embedding(query)
        results = index.query(vector=embedding, top_k=3)
        # Print results...
```

### test_vector_operations()

Test fetch and similarity operations.

```python
def test_vector_operations():
    index = pc.Index(INDEX_NAME)
    
    # Test fetch
    fetch_result = index.fetch(ids=["dispatch-ai"])
    if "dispatch-ai" in fetch_result.vectors:
        print("✓ Successfully fetched vector")
    
    # Test similarity
    for proj_id in ["dispatch-ai", "teachme-3p7bw1"]:
        vector = fetch_result.vectors[proj_id]
        similar = index.query(vector=vector.values, top_k=3)
        print(f"Similar to {proj_id}: ...")
```

### test_cleanup()

Optional cleanup of test data.

```python
def test_cleanup():
    response = input("Delete all vectors? (yes/no): ")
    if response.lower() == "yes":
        index.delete(delete_all=True)
        print("✓ All vectors deleted")
```

## Running Tests

### Full Test Suite

```bash
cd pinecone
python test_load_data.py
```

### Expected Output

```
Starting integration tests for load_data.py
============================================================
Testing API connections...
✓ OpenAI API connection successful
  Embedding dimensions: 3072
✓ Pinecone connection successful
  Index stats: {'dimension': 3072, 'total_vector_count': 25}

==================================================
Testing load_data.py workflow...
==================================================
Loading data...
Found 25 projects to load
...

--- Query: 'AI and machine learning projects' ---
1. Dispatch AI (Score: 0.856)
2. AdaptEd (Score: 0.823)
3. TalkTuahBank (Score: 0.798)
...

Integration tests completed!
```

## Manual Testing

### Test Search Quality

```python
from project_search import search_projects

queries = [
    "AI projects",
    "hackathon winners",
    "voice AI applications",
    "web development",
    "emergency response",
]

for q in queries:
    print(f"\n--- {q} ---")
    for p in search_projects(q, top_k=3):
        print(f"  {p['name']} ({p['score']:.3f})")
```

### Test Specific Project

```python
from project_search import get_project_by_id

project = get_project_by_id("dispatch-ai")
if project:
    print(f"Name: {project['name']}")
    print(f"Summary: {project['summary'][:200]}...")
else:
    print("Project not found")
```

### Check Index Stats

```python
from pinecone import Pinecone
import os

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("portfolio")
print(index.describe_index_stats())
```

## Debugging

### No Results

1. Check if data is loaded:
```python
stats = index.describe_index_stats()
print(f"Vector count: {stats['total_vector_count']}")
```

2. Verify project exists:
```python
fetch = index.fetch(ids=["project-id"])
print(fetch)
```

3. Test embedding generation:
```python
embedding = get_embedding("test query")
print(f"Embedding length: {len(embedding)}")
```

### Wrong Results

1. Check similarity scores:
```python
results = index.query(vector=embedding, top_k=10, include_metadata=True)
for m in results.matches:
    print(f"{m.id}: {m.score:.3f}")
```

Low scores (<0.5) indicate poor matches.

2. Compare embeddings:
```python
# Query embedding
q_emb = get_embedding("AI project")

# Project embedding (re-generate)
p_text = f"Project: {project['name']}\n{project['summary']}"
p_emb = get_embedding(p_text)

# Cosine similarity
similarity = sum(a*b for a,b in zip(q_emb, p_emb))
print(f"Similarity: {similarity}")
```

### API Errors

1. Check environment variables:
```python
print(f"PINECONE_API_KEY: {'set' if os.getenv('PINECONE_API_KEY') else 'missing'}")
print(f"OPENAI_API_KEY: {'set' if os.getenv('OPENAI_API_KEY') else 'missing'}")
```

2. Test API directly:
```bash
curl -H "Api-Key: $PINECONE_API_KEY" \
  https://portfolio-xxx.svc.xxx.pinecone.io/describe_index_stats
```

### Slow Queries

1. Check index region (should match deployment)
2. Consider caching frequent queries
3. Reduce `top_k` if not all results needed

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| No results | Index empty | Run `load_data.py` |
| Wrong results | Stale embeddings | Re-run `load_data.py` |
| API error | Missing env vars | Check `.env` file |
| Timeout | Network issue | Check connectivity |
| Low scores | Query mismatch | Adjust query phrasing |

## Related Files

- [functions.md](functions.md) - Search function reference
- [../data/pipeline.md](../data/pipeline.md) - Data loading
- `load_data.py` - Main loading script
