import json
from unittest.mock import patch

import pytest

from app.pipeline.llm import LLMClient
from app.pipeline.math_eval import execute_calculate_tool


# ---------------------------------------------------------------------------
# Helper: fake SSE events
# ---------------------------------------------------------------------------


class FakeSSE:
    def __init__(self, data: str):
        self.data = data


class FakeEventSource:
    """Simulates an async SSE stream."""

    def __init__(self, events: list[FakeSSE]):
        self._events = events

    async def aiter_sse(self):
        for e in self._events:
            yield e

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _content_sse(token: str) -> FakeSSE:
    """Create an SSE event for a regular content token."""
    return FakeSSE(json.dumps({
        "choices": [{"delta": {"content": token}}],
    }))


def _tool_call_start_sse(call_id: str, name: str, args_fragment: str = "") -> FakeSSE:
    """Create an SSE event for the first chunk of a tool call."""
    return FakeSSE(json.dumps({
        "choices": [{
            "delta": {
                "tool_calls": [{
                    "index": 0,
                    "id": call_id,
                    "function": {"name": name, "arguments": args_fragment},
                }],
            },
        }],
    }))


def _tool_call_args_sse(args_fragment: str) -> FakeSSE:
    """Create an SSE event for a subsequent tool-call argument chunk."""
    return FakeSSE(json.dumps({
        "choices": [{
            "delta": {
                "tool_calls": [{
                    "index": 0,
                    "function": {"arguments": args_fragment},
                }],
            },
        }],
    }))


def _done_sse() -> FakeSSE:
    return FakeSSE("[DONE]")


# ---------------------------------------------------------------------------
# Tests: LLMClient.stream_chat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_chat_regular_content():
    """Regular text tokens yield stream events with token set."""
    events = [
        _content_sse("Bonjour"),
        _content_sse(" les"),
        _content_sse(" enfants!"),
        _done_sse(),
    ]
    client = LLMClient()

    with patch("app.pipeline.llm.aconnect_sse") as mock_sse:
        mock_sse.return_value = FakeEventSource(events)
        result = []
        async for event in client.stream_chat([{"role": "user", "content": "Salut"}]):
            result.append(event)

    assert len(result) == 3
    assert all(e.token is not None for e in result)
    assert all(len(e.tool_calls) == 0 for e in result)
    assert "".join(e.token for e in result) == "Bonjour les enfants!"


@pytest.mark.asyncio
async def test_stream_chat_tool_call():
    """Tool call chunks are accumulated and yielded as a final event."""
    events = [
        _tool_call_start_sse("call_123", "calculate", '{"express'),
        _tool_call_args_sse('ion": "12 '),
        _tool_call_args_sse('* 13"}'),
        _done_sse(),
    ]
    client = LLMClient()

    with patch("app.pipeline.llm.aconnect_sse") as mock_sse:
        mock_sse.return_value = FakeEventSource(events)
        result = []
        async for event in client.stream_chat(
            [{"role": "user", "content": "12 fois 13"}],
            tools=[{"type": "function", "function": {"name": "calculate"}}],
        ):
            result.append(event)

    # Should have exactly one event: the tool call
    assert len(result) == 1
    assert len(result[0].tool_calls) == 1
    tc = result[0].tool_calls[0]
    assert tc.id == "call_123"
    assert tc.name == "calculate"
    assert json.loads(tc.arguments) == {"expression": "12 * 13"}


@pytest.mark.asyncio
async def test_stream_chat_no_tools_param():
    """When tools is None, payload should not contain 'tools' key."""
    events = [_content_sse("ok"), _done_sse()]
    client = LLMClient()

    with patch("app.pipeline.llm.aconnect_sse") as mock_sse:
        mock_sse.return_value = FakeEventSource(events)
        async for _ in client.stream_chat([{"role": "user", "content": "hi"}]):
            pass

    call_kwargs = mock_sse.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    # If called positionally
    if payload is None:
        payload = call_kwargs[0][3] if len(call_kwargs[0]) > 3 else call_kwargs.kwargs["json"]
    assert "tools" not in payload


# ---------------------------------------------------------------------------
# Tests: execute_calculate_tool
# ---------------------------------------------------------------------------


def test_execute_calculate_basic():
    result = execute_calculate_tool('{"expression": "12 * 13"}')
    assert result == "156"


def test_execute_calculate_float_to_int():
    result = execute_calculate_tool('{"expression": "10 / 2"}')
    assert result == "5"


def test_execute_calculate_keeps_float():
    result = execute_calculate_tool('{"expression": "10 / 3"}')
    assert "3.333" in result


def test_execute_calculate_invalid_json():
    result = execute_calculate_tool("not json")
    assert result.startswith("Error:")


def test_execute_calculate_unsafe_expression():
    result = execute_calculate_tool('{"expression": "__import__(\'os\')"}')
    assert result.startswith("Error:")


def test_execute_calculate_division_by_zero():
    result = execute_calculate_tool('{"expression": "1 / 0"}')
    assert result.startswith("Error:")
