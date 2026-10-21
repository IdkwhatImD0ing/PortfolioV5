"""
Integration test: ask the live backend to "show me adapted" via /chat
and verify the agent resolves the correct project ID (teachme-3p7bw1)
and emits status events during tool execution.

Requires the backend to be running on localhost:8000.

Run:
    python -m pytest tests/test_adapted_lookup.py -v -s
"""

import json
import httpx
import pytest

BASE_URL = "http://localhost:8000"
EXPECTED_PROJECT_ID = "teachme-3p7bw1"


def parse_sse_events(raw: str) -> list[dict]:
    """Parse an SSE text stream into a list of JSON payloads."""
    events = []
    for line in raw.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[len("data: "):]))
            except json.JSONDecodeError:
                continue
    return events


@pytest.fixture(scope="module")
def server_available():
    """Skip the entire module if the backend isn't reachable."""
    try:
        r = httpx.get(f"{BASE_URL}/ping", timeout=3)
        if r.status_code != 200:
            pytest.skip("Backend not reachable")
    except httpx.ConnectError:
        pytest.skip("Backend not running on localhost:8000")


@pytest.mark.integration
class TestAdaptedProjectLookup:
    """Verify the agent resolves AdaptEd and emits status events."""

    def _chat(self, messages: list[dict], timeout: float = 60) -> list[dict]:
        """Send a /chat request and return parsed SSE events."""
        with httpx.Client(base_url=BASE_URL, timeout=timeout) as client:
            resp = client.post("/chat", json={"messages": messages})
            assert resp.status_code == 200
            return parse_sse_events(resp.text)

    def test_show_adapted_resolves_correct_id(self, server_available):
        """'Show me AdaptEd' should navigate to teachme-3p7bw1."""
        events = self._chat([
            {"role": "user", "content": "Show me the AdaptEd project"},
        ])

        nav_events = [
            e for e in events
            if e.get("type") == "metadata"
            and isinstance(e.get("metadata"), dict)
            and e["metadata"].get("page") == "project"
        ]

        assert nav_events, (
            "Expected a navigation metadata event for a project page, "
            f"but none found. All events:\n{json.dumps(events, indent=2)}"
        )

        project_id = nav_events[0]["metadata"].get("project_id", "")
        assert project_id == EXPECTED_PROJECT_ID, (
            f"Expected project_id '{EXPECTED_PROJECT_ID}', got '{project_id}'"
        )

    def test_show_adapted_misspelled(self, server_available):
        """Even a casual 'show me adapted' (lowercase) should resolve correctly."""
        events = self._chat([
            {"role": "user", "content": "show me adapted"},
        ])

        nav_events = [
            e for e in events
            if e.get("type") == "metadata"
            and isinstance(e.get("metadata"), dict)
            and e["metadata"].get("page") == "project"
        ]

        assert nav_events, (
            "Expected a navigation metadata event for a project page, "
            f"but none found. All events:\n{json.dumps(events, indent=2)}"
        )

        project_id = nav_events[0]["metadata"].get("project_id", "")
        assert project_id == EXPECTED_PROJECT_ID, (
            f"Expected project_id '{EXPECTED_PROJECT_ID}', got '{project_id}'"
        )

    def test_status_events_emitted(self, server_available):
        """Stream should include status events (Thinking, tool labels) before content."""
        events = self._chat([
            {"role": "user", "content": "Show me the AdaptEd project"},
        ])

        status_events = [e for e in events if e.get("type") == "status"]
        content_events = [e for e in events if e.get("type") == "content"]

        assert status_events, (
            "Expected at least one status event, but none found. "
            f"All events:\n{json.dumps(events, indent=2)}"
        )

        assert status_events[0].get("content") == "Thinking...", (
            f"First status event should be 'Thinking...', got '{status_events[0].get('content')}'"
        )

        if content_events:
            first_status_idx = events.index(status_events[0])
            first_content_idx = events.index(content_events[0])
            assert first_status_idx < first_content_idx, (
                "Status events should appear before content events"
            )
