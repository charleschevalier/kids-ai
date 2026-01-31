from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import httpx
from httpx_sse import aconnect_sse


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
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """Yield token strings as they arrive from the LLM."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }
        async with aconnect_sse(
            self._client,
            "POST",
            f"{self.base_url}/v1/chat/completions",
            json=payload,
        ) as event_source:
            async for sse in event_source.aiter_sse():
                if sse.data == "[DONE]":
                    return
                chunk = json.loads(sse.data)
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content

    async def close(self) -> None:
        await self._client.aclose()
