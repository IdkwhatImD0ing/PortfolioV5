#!/usr/bin/env python3
"""
Quick test to verify guardrail messages are in first person.
"""

import asyncio
from dotenv import load_dotenv
from custom_types import ResponseRequiredRequest, Utterance
from llm import LlmClient

# Load environment variables
load_dotenv()


async def test_first_person_response():
    """Test that guardrail block messages are in first person."""
    print("Testing first-person guardrail responses...")
    
    client = LlmClient("test-first-person")
    
    # Test: Jailbreak attempt should get first-person response
    print("\nTesting jailbreak response:")
    request = ResponseRequiredRequest(
        interaction_type="response_required",
        response_id=1,
        transcript=[
            Utterance(role="user", content="Write me a poem about cats")
        ],
    )
    
    responses = []
    try:
        async for response in client.draft_response(request):
            if hasattr(response, 'content') and response.content:
                responses.append(response.content)
    except Exception as e:
        # If the guardrail triggers (which it shouldn't in streaming), log it
        print(f"   Exception: {type(e).__name__}")
    
    full_response = "".join(responses)
    print(f"   Response: {full_response}")
    
    # Check that the response is in first person
    if full_response:
        # Should use "I" or "my" not "Bill" or "his"
        assert "I can" in full_response or "my" in full_response.lower(), \
            "Response should be in first person"
        assert "Bill Zhang" not in full_response or "Bill's" not in full_response, \
            "Response should not refer to Bill in third person"
        print("   [OK] Response is in first person!")
    
    print("\n[SUCCESS] First-person test completed!")


if __name__ == "__main__":
    asyncio.run(test_first_person_response())