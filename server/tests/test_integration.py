"""End-to-end integration test for the voice agent WebSocket pipeline.

Mocks the ML models (VAD, STT, TTS) and LLM server so the test runs
without GPU or external services, but exercises the real Session
orchestration: async queues, state machine, sentence chunking, and
WebSocket protocol.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from fastapi import WebSocket

from app.session import Session, SharedModels

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_TRANSCRIPT = "Bonjour, raconte-moi une histoire."
FAKE_LLM_RESPONSE = "Il était une fois un petit chat. Il aimait dormir au soleil."
FAKE_TTS_AUDIO = b"\x00\x01" * 2048  # 4096 bytes of fake PCM
FAKE_TTS_SAMPLE_RATE = 24000

# ---------------------------------------------------------------------------
# Fake models that satisfy real constructors
# ---------------------------------------------------------------------------


class FakeVADModel:
    """Fake Silero VAD model. Speech flag controllable externally."""

    def __init__(self) -> None:
        self._speech = False

    def reset_states(self) -> None:
        pass

    def set_speech(self, val: bool) -> None:
        self._speech = val

    def __call__(self, chunk: Any, sample_rate: int) -> Any:
        result = MagicMock()
        result.item.return_value = 0.9 if self._speech else 0.1
        return result


class FakeWhisperModel:
    """Fake faster-whisper model. Returns a fixed transcript."""

    def transcribe(self, audio: Any, **kwargs: Any) -> tuple[list[Any], Any]:
        seg = MagicMock()
        seg.text = FAKE_TRANSCRIPT
        return [seg], MagicMock()


class FakeTTSModel:
    """Fake Chatterbox TTS model."""

    sr = 24000

    def generate(self, text: str, audio_prompt_path: str | None = None, **kwargs: Any) -> Any:
        samples = np.zeros(4096, dtype=np.float32)
        mock_tensor = MagicMock()
        mock_tensor.squeeze.return_value = mock_tensor
        mock_tensor.cpu.return_value = mock_tensor
        mock_tensor.numpy.return_value = samples
        return mock_tensor


class FakeLLMClient:
    """Yields tokens from FAKE_LLM_RESPONSE one word at a time."""

    async def stream_chat(
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        words = FAKE_LLM_RESPONSE.split(" ")
        for i, word in enumerate(words):
            token = word if i == 0 else f" {word}"
            yield token
            await asyncio.sleep(0)

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_silence(num_samples: int = 512) -> bytes:
    return b"\x00\x00" * num_samples


def _make_tone(num_samples: int = 512, freq: float = 440.0) -> bytes:
    t = np.arange(num_samples, dtype=np.float32) / 16000
    samples = (np.sin(2 * np.pi * freq * t) * 16000).astype(np.int16)
    return samples.tobytes()


def _build_session(
    ws: WebSocket,
    vad_model: FakeVADModel,
) -> Session:
    """Build a Session with fake models. The real VADProcessor, STTProcessor,
    and TTSProcessor constructors run, but with fake models that satisfy them.
    Only the LLM client is replaced entirely (it's an HTTP client, not a model)."""
    shared = SharedModels(
        vad_model=vad_model,
        whisper_model=FakeWhisperModel(),
        tts_model=FakeTTSModel(),
    )
    session = Session(ws, shared)
    # Replace LLM client (the real one tries to connect via HTTP)
    session.llm = FakeLLMClient()  # type: ignore[assignment]
    return session


def _mock_ws() -> tuple[AsyncMock, asyncio.Queue[dict[str, Any]], list[dict[str, Any]], list[bytes]]:
    """Create a mock WebSocket and return (ws, client_msg_queue, sent_json, sent_bytes)."""
    ws = AsyncMock(spec=WebSocket)
    sent_json: list[dict[str, Any]] = []
    sent_bytes: list[bytes] = []
    client_messages: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def _send_json(data: Any) -> None:
        sent_json.append(data)

    async def _send_bytes(data: bytes) -> None:
        sent_bytes.append(data)

    async def _receive() -> dict[str, Any]:
        return await client_messages.get()

    ws.send_json = _send_json
    ws.send_bytes = _send_bytes
    ws.receive = _receive

    return ws, client_messages, sent_json, sent_bytes


async def _send_speech_then_silence(
    vad: FakeVADModel,
    client_messages: asyncio.Queue[dict[str, Any]],
    speech_frames: int = 10,
    silence_frames: int = 25,
) -> None:
    """Simulate a speech utterance followed by silence."""
    vad.set_speech(True)
    for _ in range(speech_frames):
        await client_messages.put({
            "type": "websocket.receive",
            "bytes": _make_tone(),
        })
        await asyncio.sleep(0.005)

    vad.set_speech(False)
    for _ in range(silence_frames):
        await client_messages.put({
            "type": "websocket.receive",
            "bytes": _make_silence(),
        })
        await asyncio.sleep(0.005)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_speech_to_audio() -> None:
    """Full turn: speech audio in -> state transitions + transcript + TTS audio out."""
    ws, client_messages, sent_json, sent_bytes = _mock_ws()
    vad = FakeVADModel()
    session = _build_session(ws, vad)

    session_task = asyncio.create_task(session.run())
    await asyncio.sleep(0.05)

    # Simulate one speech turn
    await _send_speech_then_silence(vad, client_messages)

    # Wait for the pipeline to complete (STT -> LLM -> sentence_chunker -> TTS -> send)
    await asyncio.sleep(1.0)

    # Disconnect
    await client_messages.put({"type": "websocket.disconnect"})
    await asyncio.wait_for(session_task, timeout=3.0)
    await session.cleanup()

    # --- Assertions ---

    # 1) First message is tts_config
    assert sent_json[0]["type"] == "tts_config"
    assert sent_json[0]["sample_rate"] == FAKE_TTS_SAMPLE_RATE

    # 2) State transitions: LISTENING -> THINKING -> SPEAKING -> IDLE
    state_msgs = [m for m in sent_json if m.get("type") == "state"]
    states = [m["state"] for m in state_msgs]
    assert "LISTENING" in states
    assert "THINKING" in states
    assert "SPEAKING" in states
    assert "IDLE" in states
    # Correct order
    assert states.index("LISTENING") < states.index("THINKING")
    assert states.index("THINKING") < states.index("SPEAKING")
    assert states.index("SPEAKING") < len(states) - 1 - states[::-1].index("IDLE")

    # 3) User transcript
    user_msgs = [
        m for m in sent_json
        if m.get("type") == "transcript" and m.get("role") == "user"
    ]
    assert len(user_msgs) == 1
    assert user_msgs[0]["text"] == FAKE_TRANSCRIPT

    # 4) Assistant transcript
    assistant_msgs = [
        m for m in sent_json
        if m.get("type") == "transcript" and m.get("role") == "assistant"
    ]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0]["text"] == FAKE_LLM_RESPONSE

    # 5) TTS audio was sent
    assert len(sent_bytes) > 0
    total_audio = sum(len(b) for b in sent_bytes)
    assert total_audio > 0


@pytest.mark.asyncio
async def test_barge_in_cancels_response() -> None:
    """New speech during SPEAKING triggers barge-in and resets to IDLE."""
    ws, client_messages, sent_json, _ = _mock_ws()
    vad = FakeVADModel()

    # Slow LLM to give us time to interrupt
    class SlowLLM:
        async def stream_chat(
            self, messages: list[dict[str, str]]
        ) -> AsyncGenerator[str, None]:
            for word in "Ceci est une très longue réponse qui prend du temps.".split():
                yield f" {word}"
                await asyncio.sleep(0.08)

        async def close(self) -> None:
            pass

    session = _build_session(ws, vad)
    session.llm = SlowLLM()  # type: ignore[assignment]

    session_task = asyncio.create_task(session.run())
    await asyncio.sleep(0.05)

    # Send first utterance
    await _send_speech_then_silence(vad, client_messages)

    # Wait until SPEAKING
    for _ in range(60):
        if any(
            m.get("type") == "state" and m.get("state") == "SPEAKING"
            for m in sent_json
        ):
            break
        await asyncio.sleep(0.05)

    # Now send new speech (barge-in)
    vad.set_speech(True)
    await client_messages.put({
        "type": "websocket.receive",
        "bytes": _make_tone(),
    })
    await asyncio.sleep(0.2)

    # Verify IDLE appears after SPEAKING (barge-in reset)
    state_msgs = [m for m in sent_json if m.get("type") == "state"]
    states = [m["state"] for m in state_msgs]

    speaking_indices = [i for i, s in enumerate(states) if s == "SPEAKING"]
    idle_after_speaking = [
        i for i, s in enumerate(states)
        if s == "IDLE" and any(i > si for si in speaking_indices)
    ]
    assert len(idle_after_speaking) > 0, (
        f"Expected IDLE after SPEAKING (barge-in). States: {states}"
    )

    # Disconnect
    vad.set_speech(False)
    await client_messages.put({"type": "websocket.disconnect"})
    try:
        await asyncio.wait_for(session_task, timeout=3.0)
    except Exception:
        pass
    await session.cleanup()


@pytest.mark.asyncio
async def test_disconnect_shuts_down_cleanly() -> None:
    """Immediate disconnect doesn't hang or crash."""
    ws, client_messages, sent_json, _ = _mock_ws()
    vad = FakeVADModel()
    session = _build_session(ws, vad)

    session_task = asyncio.create_task(session.run())
    await asyncio.sleep(0.05)

    # Disconnect immediately
    await client_messages.put({"type": "websocket.disconnect"})

    # Should complete within timeout
    await asyncio.wait_for(session_task, timeout=3.0)
    await session.cleanup()

    # tts_config should still have been sent
    assert any(m.get("type") == "tts_config" for m in sent_json)
