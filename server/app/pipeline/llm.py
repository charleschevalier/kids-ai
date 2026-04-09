from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import httpx
from httpx_sse import aconnect_sse


@dataclass
class ToolCall:
    """A tool call extracted from the LLM streaming response."""

    id: str
    name: str
    arguments: str


@dataclass
class StreamEvent:
    """A single event from the LLM stream.

    Exactly one of ``token`` or ``tool_calls`` is set.
    """

    token: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient:
    """Async streaming client for llama.cpp's OpenAI-compatible API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        model: str = "local-model",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = httpx.AsyncClient(timeout=60.0)

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Yield ``StreamEvent`` objects as they arrive from the LLM.

        When *tools* is provided the model may choose to call a tool instead of
        producing text.  In that case the **last** yielded event will carry one
        or more ``ToolCall`` objects.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        # Accumulate tool-call fragments across SSE chunks.
        pending_tool_calls: dict[int, dict[str, str]] = {}

        async with aconnect_sse(
            self._client,
            "POST",
            f"{self.base_url}/v1/chat/completions",
            json=payload,
        ) as event_source:
            async for sse in event_source.aiter_sse():
                if sse.data == "[DONE]":
                    break
                chunk = json.loads(sse.data)
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})

                # --- regular content token ---
                content = delta.get("content")
                if content:
                    yield StreamEvent(token=content)

                # --- tool-call fragments ---
                for tc in delta.get("tool_calls", []):
                    idx = tc.get("index", 0)
                    if idx not in pending_tool_calls:
                        pending_tool_calls[idx] = {
                            "id": tc.get("id", ""),
                            "name": tc.get("function", {}).get("name", ""),
                            "arguments": "",
                        }
                    else:
                        # id and name may arrive only in the first chunk
                        if tc.get("id"):
                            pending_tool_calls[idx]["id"] = tc["id"]
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            pending_tool_calls[idx]["name"] = fn["name"]
                    # argument tokens are streamed incrementally
                    fn_args = tc.get("function", {}).get("arguments", "")
                    if fn_args:
                        pending_tool_calls[idx]["arguments"] += fn_args

        # Emit accumulated tool calls (if any) as a final event.
        if pending_tool_calls:
            calls = [
                ToolCall(
                    id=v["id"],
                    name=v["name"],
                    arguments=v["arguments"],
                )
                for v in pending_tool_calls.values()
            ]
            yield StreamEvent(tool_calls=calls)

    async def close(self) -> None:
        await self._client.aclose()
