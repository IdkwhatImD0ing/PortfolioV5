import asyncio
import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pinecone import Pinecone

load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

pc = Pinecone(api_key=PINECONE_API_KEY)
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

INDEX_NAME = "portfolio"


async def test_connection():
    """Test connections to OpenAI and Pinecone."""
    print("Testing API connections...")

    try:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-large", input="test connection"
        )
        print("✓ OpenAI API connection successful")
        print(f"  Embedding dimensions: {len(response.data[0].embedding)}")
    except Exception as e:
        print(f"✗ OpenAI API connection failed: {e}")
        return False

    try:
        index = pc.Index(INDEX_NAME)
        stats = await asyncio.to_thread(index.describe_index_stats)
        print("✓ Pinecone connection successful")
        print(f"  Index stats: {stats}")
    except Exception as e:
        print(f"✗ Pinecone connection failed: {e}")
        return False

    return True


async def test_load_and_query():
    """Test the full load_data.py workflow."""
    print("\n" + "=" * 50)
    print("Testing load_data.py workflow...")
    print("=" * 50)

    print("\n1. Running load_data.py to load data...")
    import load_data

    await load_data.main()

    print("\n2. Testing various queries against loaded data...")

    test_queries = [
        "AI and machine learning projects",
        "web development full stack",
        "mobile app development",
        "data analysis and visualization",
        "real-time applications",
        "interview preparation coaching",
    ]

    index = pc.Index(INDEX_NAME)

    for query_text in test_queries:
        print(f"\n--- Query: '{query_text}' ---")

        query_embedding = await load_data.get_embedding(query_text)

        results = await asyncio.to_thread(
            index.query,
            vector=query_embedding,
            top_k=3,
            include_metadata=True,
        )

        if results.matches:
            for i, match in enumerate(results.matches, 1):
                print(
                    f"{i}. {match.metadata.get('name', 'Unknown')} (Score: {match.score:.3f})"
                )
                print(
                    f"   Summary: {match.metadata.get('summary', 'No summary')[:100]}..."
                )
                if match.metadata.get("github"):
                    print(f"   GitHub: {match.metadata.get('github')}")
                if match.metadata.get("demo"):
                    print(f"   Demo: {match.metadata.get('demo')}")
        else:
            print("   No matches found")

        await asyncio.sleep(0.5)


async def test_vector_operations():
    """Test specific vector operations."""
    print("\n" + "=" * 50)
    print("Testing vector operations...")
    print("=" * 50)

    index = pc.Index(INDEX_NAME)

    print("\n1. Testing fetch operation...")
    try:
        test_id = "dispatch-ai"
        fetch_result = await asyncio.to_thread(index.fetch, ids=[test_id])

        if test_id in fetch_result.vectors:
            vector_data = fetch_result.vectors[test_id]
            print(f"✓ Successfully fetched vector '{test_id}'")
            print(f"  Metadata: {vector_data.metadata}")
        else:
            print(f"✗ Vector '{test_id}' not found")
    except Exception as e:
        print(f"✗ Fetch operation failed: {e}")

    print("\n2. Testing similarity between projects...")
    project_ids = ["dispatch-ai", "courtvision-gtui7w", "sentinelai-dec0jp"]

    for proj_id in project_ids:
        try:
            fetch_result = await asyncio.to_thread(index.fetch, ids=[proj_id])
            if proj_id in fetch_result.vectors:
                vector = fetch_result.vectors[proj_id]

                similar = await asyncio.to_thread(
                    index.query,
                    vector=vector.values,
                    top_k=3,
                    include_metadata=True,
                    filter={"id": {"$ne": proj_id}},
                )

                print(
                    f"\nProjects similar to '{vector.metadata.get('name', proj_id)}':"
                )
                for match in similar.matches:
                    if match.id != proj_id:
                        print(
                            f"  - {match.metadata.get('name')} (Score: {match.score:.3f})"
                        )
        except Exception as e:
            print(f"Error processing {proj_id}: {e}")


def test_cleanup():
    """Optional: Clean up test data from Pinecone."""
    print("\n" + "=" * 50)
    print("Cleanup options...")
    print("=" * 50)

    response = input("\nDo you want to delete all vectors from the index? (yes/no): ")

    if response.lower() == "yes":
        try:
            index = pc.Index(INDEX_NAME)
            index.delete(delete_all=True)
            print("✓ All vectors deleted from index")

            stats = index.describe_index_stats()
            print(f"  Index stats after deletion: {stats}")
        except Exception as e:
            print(f"✗ Failed to delete vectors: {e}")
    else:
        print("Skipping cleanup")


async def run():
    print("Starting integration tests for load_data.py")
    print("=" * 60)

    if not await test_connection():
        print(
            "\nConnection tests failed. Please check your API keys and network connection."
        )
        raise SystemExit(1)

    await test_load_and_query()
    await test_vector_operations()

    test_cleanup()

    print("\n" + "=" * 60)
    print("Integration tests completed!")


if __name__ == "__main__":
    asyncio.run(run())
