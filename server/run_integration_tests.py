#!/usr/bin/env python3
"""
Integration test runner for LLM client - tests actual API calls.
Make sure you have the required environment variables set before running:
- OPENAI_API_KEY

Run from the server directory:
    python run_integration_tests.py [--debug-llm] [--plain]
"""

import asyncio
import argparse
import json
import os
from datetime import datetime
import traceback

# Since we're running from the server directory, imports should work directly
from custom_types import (
    ResponseRequiredRequest,
    ResponseResponse,
    Utterance,
    ToolCallInvocationResponse,
    ToolCallResultResponse,
    MetadataResponse,
)
from llm import LlmClient
from dotenv import load_dotenv

load_dotenv()


class Colors:
    """ANSI color codes for prettier output."""

    GREEN = "\033[92m"
    BLUE = "\033[94m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    END = "\033[0m"
    BOLD = "\033[1m"


def set_colors_enabled(enabled: bool):
    if not enabled:
        for attr in (
            "GREEN",
            "BLUE",
            "YELLOW",
            "RED",
            "CYAN",
            "MAGENTA",
            "END",
            "BOLD",
        ):
            setattr(Colors, attr, "")


async def test_basic_functionality(client: LlmClient):
    """Test basic LLM client functionality."""
    print(f"\n{Colors.CYAN}=== Testing Basic Functionality ==={Colors.END}")

    # Test 1: Begin message
    print(f"\n{Colors.YELLOW}1. Testing begin message:{Colors.END}")
    response = client.draft_begin_message()
    print(f"   Begin message: {Colors.GREEN}{response.content[:50]}...{Colors.END}")
    print(f"   Response ID: {response.response_id}")

    # Test 2: Transcript conversion
    print(f"\n{Colors.YELLOW}2. Testing transcript conversion:{Colors.END}")
    test_transcript = [
        Utterance(role="user", content="Hello"),
        Utterance(role="agent", content="Hi there!"),
    ]
    messages = client.convert_transcript_to_openai_messages(test_transcript)
    print(f"   Converted {len(test_transcript)} utterances to {len(messages)} messages")

    return True


async def test_simple_chat(client: LlmClient):
    """Test a simple chat interaction."""
    print(f"\n{Colors.CYAN}=== Testing Simple Chat ==={Colors.END}")

    request = ResponseRequiredRequest(
        interaction_type="response_required",
        response_id=1,
        transcript=[
            Utterance(
                role="user", content="Hi Bill! Tell me about yourself in one sentence."
            )
        ],
    )

    print(f"User: {Colors.BLUE}{request.transcript[0].content}{Colors.END}")
    print(f"Bill: ", end="", flush=True)

    response_count = 0
    async for response in client.draft_response(request):
        if isinstance(response, ResponseResponse):
            if response.content:
                print(
                    f"{Colors.GREEN}{response.content}{Colors.END}", end="", flush=True
                )
            response_count += 1

    print(f"\n{Colors.YELLOW}(Received {response_count} response chunks){Colors.END}")
    return True


async def test_tool_calls(client: LlmClient):
    """Test tool calling functionality."""
    print(f"\n{Colors.CYAN}=== Testing Tool Calls ==={Colors.END}")

    test_prompts = [
        ("Show me your homepage", "display_homepage"),
        ("Display your education", "display_education_page"),
        ("Show me the SlugLoop project", "display_project"),
    ]

    for prompt, expected_tool in test_prompts:
        print(f"\n{Colors.YELLOW}Testing: '{prompt}'{Colors.END}")

        request = ResponseRequiredRequest(
            interaction_type="response_required",
            response_id=10,
            transcript=[Utterance(role="user", content=prompt)],
        )

        tool_called = False
        message_parts = []

        async for response in client.draft_response(request):
            if isinstance(response, ResponseResponse) and response.content:
                message_parts.append(response.content)

            elif isinstance(response, ToolCallInvocationResponse):
                tool_called = True
                print(f"   {Colors.GREEN}[OK] Tool called: {response.name}{Colors.END}")
                if response.name == expected_tool:
                    print(f"   {Colors.GREEN}[OK] Correct tool!{Colors.END}")
                else:
                    print(f"   {Colors.RED}[FAIL] Expected: {expected_tool}{Colors.END}")

            elif isinstance(response, ToolCallResultResponse):
                print(f"   Tool result: {response.content}")

        if message_parts:
            full_message = "".join(message_parts)
            print(f"   Message: {Colors.CYAN}{full_message[:100]}...{Colors.END}")

        if not tool_called:
            print(f"   {Colors.RED}[FAIL] No tool was called{Colors.END}")

    return True


async def test_conversation_flow(client: LlmClient):
    """Test a multi-turn conversation."""
    print(f"\n{Colors.CYAN}=== Testing Conversation Flow ==={Colors.END}")

    conversation = [
        Utterance(role="user", content="Hi Bill!"),
        Utterance(
            role="agent",
            content="Hey! I'm Bill Zhang, engineer and hackathon enthusiast.",
        ),
        Utterance(
            role="user",
            content="Tell me about your hackathon wins and show me a project",
        ),
    ]

    request = ResponseRequiredRequest(
        interaction_type="response_required", response_id=100, transcript=conversation
    )

    print("Conversation history:")
    for utt in conversation[:-1]:  # Show all but the last user message
        color = Colors.BLUE if utt.role == "user" else Colors.GREEN
        print(f"  {color}{utt.role.upper()}: {utt.content}{Colors.END}")

    print(f"\nLatest user message:")
    print(f"  {Colors.BLUE}USER: {conversation[-1].content}{Colors.END}")

    print(f"\n{Colors.YELLOW}Bill's response:{Colors.END}")

    tool_count = 0
    message_buffer = ""

    async for response in client.draft_response(request):
        if isinstance(response, ResponseResponse) and response.content:
            message_buffer += response.content
            print(f"{Colors.GREEN}{response.content}{Colors.END}", end="", flush=True)

        elif isinstance(response, ToolCallInvocationResponse):
            tool_count += 1
            print(f"\n\n{Colors.CYAN}[Tool: {response.name}]{Colors.END}")

        elif isinstance(response, ToolCallResultResponse):
            print(f" -> {response.content}")
            print("")  # New line to continue message

    print(f"\n\n{Colors.YELLOW}Summary: {tool_count} tools called{Colors.END}")
    return True


async def test_project_search(client: LlmClient):
    """Test project search functionality."""
    print(f"\n{Colors.CYAN}=== Testing Project Search ==={Colors.END}")
    
    search_queries = [
        "Show me AI projects",
        "What hackathon projects have you won with?",
        "Find me some web development projects",
        "Tell me about your machine learning work"
    ]
    
    for query in search_queries:
        print(f"\n{Colors.YELLOW}Testing search: '{query}'{Colors.END}")
        
        request = ResponseRequiredRequest(
            interaction_type="response_required",
            response_id=300,
            transcript=[Utterance(role="user", content=query)]
        )
        
        search_tool_called = False
        message_parts = []
        tool_arguments = None
        
        async for response in client.draft_response(request):
            if isinstance(response, ResponseResponse) and response.content:
                message_parts.append(response.content)
            
            elif isinstance(response, ToolCallInvocationResponse):
                if response.name == "search_projects":
                    search_tool_called = True
                    tool_arguments = response.arguments
                    print(f"   {Colors.GREEN}[OK] search_projects called{Colors.END}")
                    # Try to parse the arguments
                    try:
                        import json
                        args = json.loads(tool_arguments)
                        print(f"   Search query: {Colors.CYAN}{args.get('query', 'N/A')}{Colors.END}")
                    except:
                        print(f"   Arguments: {tool_arguments}")
            
            elif isinstance(response, ToolCallResultResponse):
                # Show first 150 chars of results
                result_preview = response.content[:150] if response.content else "No results"
                print(f"   Results preview: {Colors.MAGENTA}{result_preview}...{Colors.END}")
        
        if message_parts:
            full_message = "".join(message_parts)
            print(f"   Response excerpt: {Colors.GREEN}{full_message[:100]}...{Colors.END}")
        
        if not search_tool_called:
            print(f"   {Colors.YELLOW}[Note] search_projects was not called (may have used other approach){Colors.END}")
    
    return True


async def test_display_project_with_id(client: LlmClient):
    """Test display_project functionality with specific IDs."""
    print(f"\n{Colors.CYAN}=== Testing Display Project with ID ==={Colors.END}")
    
    test_cases = [
        ("Show me the InterviewGPT project", "interviewgpt"),
        ("Display the GetItDone project", "getitdone"),
        ("Can you show me AssignmentTracker?", "assignmenttracker"),
    ]
    
    for prompt, expected_id in test_cases:
        print(f"\n{Colors.YELLOW}Testing: '{prompt}'{Colors.END}")
        print(f"   Expected project ID: {Colors.CYAN}{expected_id}{Colors.END}")
        
        request = ResponseRequiredRequest(
            interaction_type="response_required",
            response_id=400,
            transcript=[Utterance(role="user", content=prompt)]
        )
        
        display_called = False
        project_id_sent = None
        metadata_received = False
        
        async for response in client.draft_response(request):
            if isinstance(response, ToolCallInvocationResponse):
                if response.name == "display_project":
                    display_called = True
                    print(f"   {Colors.GREEN}[OK] display_project called{Colors.END}")
                    # Parse arguments to get project ID
                    try:
                        import json
                        args = json.loads(response.arguments)
                        project_id_sent = args.get("id", "")
                        print(f"   Project ID sent: {Colors.CYAN}{project_id_sent}{Colors.END}")
                        
                        if project_id_sent.lower() == expected_id.lower():
                            print(f"   {Colors.GREEN}[OK] Correct project ID!{Colors.END}")
                        else:
                            print(f"   {Colors.YELLOW}[WARN] Different ID than expected{Colors.END}")
                    except Exception as e:
                        print(f"   {Colors.RED}Error parsing arguments: {e}{Colors.END}")
            
            elif isinstance(response, MetadataResponse):
                metadata_received = True
                if response.metadata.get("type") == "navigation":
                    page = response.metadata.get("page")
                    proj_id = response.metadata.get("project_id", "")
                    print(f"   {Colors.GREEN}[OK] Metadata sent - Page: {page}, Project ID: {proj_id}{Colors.END}")
        
        if not display_called:
            print(f"   {Colors.RED}[FAIL] display_project was not called{Colors.END}")
        
        if not metadata_received:
            print(f"   {Colors.YELLOW}[Note] No metadata response received{Colors.END}")
    
    return True


async def test_search_and_display_flow(client: LlmClient):
    """Test the complete flow of searching for projects then displaying one."""
    print(f"\n{Colors.CYAN}=== Testing Search and Display Flow ==={Colors.END}")
    
    # Multi-step conversation
    conversation = [
        Utterance(role="user", content="What AI projects have you worked on?"),
    ]
    
    print(f"{Colors.YELLOW}Step 1: Search for AI projects{Colors.END}")
    print(f"User: {Colors.BLUE}{conversation[0].content}{Colors.END}")
    
    request = ResponseRequiredRequest(
        interaction_type="response_required",
        response_id=500,
        transcript=conversation
    )
    
    search_called = False
    projects_found = []
    agent_response = ""
    
    print(f"Bill: ", end="", flush=True)
    async for response in client.draft_response(request):
        if isinstance(response, ResponseResponse) and response.content:
            agent_response += response.content
            print(f"{Colors.GREEN}{response.content}{Colors.END}", end="", flush=True)
        
        elif isinstance(response, ToolCallInvocationResponse):
            if response.name == "search_projects":
                search_called = True
                print(f"\n{Colors.CYAN}[Tool: search_projects]{Colors.END}", end="")
        
        elif isinstance(response, ToolCallResultResponse):
            # Extract project names from results if possible
            if "InterviewGPT" in response.content:
                projects_found.append("interviewgpt")
            if "GetItDone" in response.content:
                projects_found.append("getitdone")
            print(f" -> Found {len(projects_found)} projects")
    
    print(f"\n\n{Colors.YELLOW}Step 2: Request to see a specific project{Colors.END}")
    
    # Add the agent's response to conversation
    conversation.append(Utterance(role="agent", content=agent_response))
    
    # User asks to see a specific project
    if projects_found:
        user_request = f"Show me more about the first project you mentioned"
    else:
        user_request = "Can you display the InterviewGPT project?"
    
    conversation.append(Utterance(role="user", content=user_request))
    print(f"User: {Colors.BLUE}{user_request}{Colors.END}")
    
    request2 = ResponseRequiredRequest(
        interaction_type="response_required",
        response_id=501,
        transcript=conversation
    )
    
    display_called = False
    project_displayed = None
    
    print(f"Bill: ", end="", flush=True)
    async for response in client.draft_response(request2):
        if isinstance(response, ResponseResponse) and response.content:
            print(f"{Colors.GREEN}{response.content}{Colors.END}", end="", flush=True)
        
        elif isinstance(response, ToolCallInvocationResponse):
            if response.name == "display_project":
                display_called = True
                try:
                    import json
                    args = json.loads(response.arguments)
                    project_displayed = args.get("id", "")
                    print(f"\n{Colors.CYAN}[Tool: display_project(id='{project_displayed}')]{Colors.END}")
                except:
                    print(f"\n{Colors.CYAN}[Tool: display_project]{Colors.END}")
        
        elif isinstance(response, MetadataResponse):
            if response.metadata.get("type") == "navigation":
                print(f" -> Frontend navigation triggered")
    
    print(f"\n\n{Colors.YELLOW}Flow Summary:{Colors.END}")
    print(f"   Search called: {Colors.GREEN if search_called else Colors.RED}{'Yes' if search_called else 'No'}{Colors.END}")
    print(f"   Projects found: {len(projects_found)}")
    print(f"   Display called: {Colors.GREEN if display_called else Colors.RED}{'Yes' if display_called else 'No'}{Colors.END}")
    if project_displayed:
        print(f"   Project displayed: {Colors.CYAN}{project_displayed}{Colors.END}")
    
    return True


async def test_error_scenarios(client: LlmClient):
    """Test error handling scenarios."""
    print(f"\n{Colors.CYAN}=== Testing Error Scenarios ==={Colors.END}")

    # Empty transcript
    print(f"\n{Colors.YELLOW}1. Empty transcript:{Colors.END}")
    request = ResponseRequiredRequest(
        interaction_type="response_required", response_id=200, transcript=[]
    )

    try:
        response_count = 0
        async for response in client.draft_response(request):
            response_count += 1
        print(
            f"   {Colors.GREEN}[OK] Handled empty transcript (got {response_count} responses){Colors.END}"
        )
    except Exception as e:
        print(f"   {Colors.RED}[FAIL] Error: {e}{Colors.END}")

    # Very long input
    print(f"\n{Colors.YELLOW}2. Long conversation history:{Colors.END}")
    long_transcript = []
    for i in range(20):
        long_transcript.append(
            Utterance(
                role="user" if i % 2 == 0 else "agent",
                content=f"Message {i}: Some conversation content here...",
            )
        )

    request = ResponseRequiredRequest(
        interaction_type="response_required",
        response_id=201,
        transcript=long_transcript,
    )

    try:
        response_count = 0
        async for response in client.draft_response(request):
            response_count += 1
            if (
                response_count == 1
                and isinstance(response, ResponseResponse)
                and response.content
            ):
                print(
                    f"   First response: {Colors.GREEN}{response.content[:50]}...{Colors.END}"
                )
        print(
            f"   {Colors.GREEN}[OK] Handled long conversation (got {response_count} responses){Colors.END}"
        )
    except Exception as e:
        print(f"   {Colors.RED}[FAIL] Error: {e}{Colors.END}")

    return True


async def main(args) -> int:
    """Run all integration tests."""
    # Configure output and LLM debug
    set_colors_enabled(not getattr(args, "no_color", False))
    if getattr(args, "debug_llm", False):
        os.environ["LLM_DEBUG"] = "1"
    else:
        os.environ.setdefault("LLM_DEBUG", "0")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}LLM Client Integration Tests{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(
        f"{Colors.YELLOW}Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}"
    )

    # Check environment variables
    required_vars = ["OPENAI_API_KEY", "PINECONE_API_KEY"]
    missing = [var for var in required_vars if not os.environ.get(var)]

    if missing:
        print(f"\n{Colors.RED}Missing environment variables:{Colors.END}")
        for var in missing:
            print(f"   - {var}")
        print(f"\n{Colors.YELLOW}Set these variables and try again.{Colors.END}")
        return 1

    print(f"\n{Colors.GREEN}[OK] All environment variables present{Colors.END}")

    # Initialize client
    try:
        client = LlmClient("test-call-id", debug=(os.getenv("LLM_DEBUG") == "1"))
        print(f"{Colors.GREEN}[OK] LLM Client initialized{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}[FAIL] Failed to initialize: {e}{Colors.END}")
        return 1

    # Run tests
    tests = [
        ("Basic Functionality", test_basic_functionality),
        ("Simple Chat", test_simple_chat),
        ("Tool Calls", test_tool_calls),
        ("Project Search", test_project_search),
        ("Display Project with ID", test_display_project_with_id),
        ("Search and Display Flow", test_search_and_display_flow),
        ("Conversation Flow", test_conversation_flow),
        ("Error Scenarios", test_error_scenarios),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
            await test_func(client)
            results.append((test_name, True, None))
            print(f"\n{Colors.GREEN}[OK] {test_name} completed{Colors.END}")
        except Exception as e:
            results.append((test_name, False, str(e)))
            print(f"\n{Colors.RED}[FAIL] {test_name} failed: {e}{Colors.END}")
            traceback.print_exc()

    # Summary
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}Test Summary{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")

    passed = sum(1 for _, success, _ in results if success)
    failed = len(results) - passed

    for test_name, success, error in results:
        status = (
            f"{Colors.GREEN}[PASS]{Colors.END}"
            if success
            else f"{Colors.RED}[FAIL]{Colors.END}"
        )
        print(f"{status} {test_name}")
        if error:
            print(f"       {Colors.RED}{error[:60]}...{Colors.END}")

    print(f"\n{Colors.BOLD}Results:{Colors.END}")
    print(f"  {Colors.GREEN}Passed: {passed}{Colors.END}")
    print(f"  {Colors.RED}Failed: {failed}{Colors.END}")
    print(f"  Total: {len(results)}")

    if failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed!{Colors.END}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}Some tests failed{Colors.END}")

    print(
        f"\n{Colors.YELLOW}Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LLM client integration tests")
    parser.add_argument(
        "--debug-llm", action="store_true", help="Show verbose LLM streaming debug logs"
    )
    parser.add_argument(
        "--plain",
        "--no-color",
        dest="no_color",
        action="store_true",
        help="Disable colored output",
    )
    args = parser.parse_args()
    # Try to enable Windows ANSI colors if colorama is installed
    if not args.no_color and os.name == "nt":
        try:
            import colorama  # type: ignore

            colorama.just_fix_windows_console()
        except Exception:
            pass
    raise SystemExit(asyncio.run(main(args)))
