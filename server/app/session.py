from __future__ import annotations

import asyncio
import enum
import json
import logging
import re
from typing import Any

from fastapi import WebSocket

from app.config import settings
from app.pipeline.llm import LLMClient, StreamEvent, ToolCall
from app.pipeline.math_eval import execute_calculate_tool
from app.pipeline.sentence_chunker import SentenceChunker
from app.pipeline.stt import STTProcessor
from app.pipeline.tts import TTSProcessor
from app.pipeline.vad import VADProcessor

logger = logging.getLogger(__name__)

# Regex to strip emojis and miscellaneous symbols from LLM output.
def _sanitize_for_tts(text: str) -> str:
    """Clean text for TTS synthesis.

    Chatterbox handles punctuation and numbers natively,
    so we only collapse whitespace here.
    """
    text = text.replace("**", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


_EMOJI_RE = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map
    "\U0001f1e0-\U0001f1ff"  # flags
    "\U0001f900-\U0001f9ff"  # supplemental symbols
    "\U0001fa00-\U0001fa6f"  # chess symbols
    "\U0001fa70-\U0001faff"  # symbols extended-A
    "\U00002702-\U000027b0"  # dingbats
    "\U0000fe00-\U0000fe0f"  # variation selectors
    "\U0000200d"             # zero-width joiner
    "\U000020e3"             # combining enclosing keycap
    "\U00002600-\U000026ff"  # misc symbols
    "\U00002300-\U000023ff"  # misc technical
    "]+",
    flags=re.UNICODE,
)

# Size of binary audio chunks sent to the client (bytes).
_WS_AUDIO_CHUNK = 4096

# Tool definition for the calculate tool (OpenAI function-calling format).
_CALCULATE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "Evaluate a math expression and return the numeric result. Use this for any arithmetic question.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A math expression using numbers and operators, e.g. '12 * 13' or '145 + 278'",
                },
            },
            "required": ["expression"],
        },
    },
}

_TOOLS = [_CALCULATE_TOOL]


class SessionState(enum.Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"


class SharedModels:
    """Models loaded once at app startup and shared across sessions."""

    def __init__(
        self,
        vad_model: Any,
        whisper_model: Any,
        whisper_processor: Any,
        tts_model: Any,
        grammar_tool: Any = None,
    ) -> None:
        self.vad_model: Any = vad_model
        self.whisper_model: Any = whisper_model
        self.whisper_processor: Any = whisper_processor
        self.tts_model: Any = tts_model
        self.grammar_tool: Any = grammar_tool


class Session:
    """One WebSocket conversation session.

    Owns the full async pipeline:
        receive_loop -> VAD -> STT -> LLM -> sentence_chunker -> TTS -> send audio
    Connected by asyncio.Queues.
    """

    def __init__(self, ws: WebSocket, shared: SharedModels) -> None:
        self.ws = ws
        self.state = SessionState.IDLE

        # Pipeline processors
        self.vad = VADProcessor(
            shared.vad_model,
            sample_rate=settings.sample_rate,
            threshold=settings.vad_threshold,
            min_silence_ms=settings.vad_min_silence_ms,
            min_speech_ms=settings.vad_min_speech_ms,
        )
        self.stt = STTProcessor(
            shared.whisper_model,
            shared.whisper_processor,
            language=settings.whisper_language,
            beam_size=settings.whisper_beam_size,
        )
        self.llm = LLMClient(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )
        self.tts = TTSProcessor(
            shared.tts_model,
            speaker_wav=settings.tts_speaker_wav,
            sentence_silence=settings.tts_sentence_silence,
            exaggeration=settings.tts_exaggeration,
            temperature=settings.tts_temperature,
            cfg_weight=settings.tts_cfg_weight,
        )

        # Inter-stage queues
        self.audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=4)
        self.text_queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=4)
        self.sentence_queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=16)
        self.tts_audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=32)

        # Conversation history (system prompt is refreshed before each LLM call
        # so the joke selection rotates).
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": settings.get_system_prompt()},
        ]

        # Grammar correction (shared LanguageTool instance)
        self._grammar_tool = shared.grammar_tool

        # Cancellation and shutdown
        self._cancel = asyncio.Event()
        self._done = False

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Run all pipeline stages concurrently until the WS closes."""
        # Tell the client the TTS audio format
        await self._send_json(
            type="tts_config",
            sample_rate=self.tts.sample_rate,
            channels=1,
            format="s16le",
        )

        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._receive_loop())
            tg.create_task(self._stt_worker())
            tg.create_task(self._llm_worker())
            tg.create_task(self._tts_worker())
            tg.create_task(self._audio_send_loop())

    async def cleanup(self) -> None:
        await self.llm.close()

    # ------------------------------------------------------------------
    # Stage 1: Receive audio + control messages, run VAD
    # ------------------------------------------------------------------

    async def _receive_loop(self) -> None:
        while True:
            message = await self.ws.receive()
            msg_type = message.get("type", "")

            if msg_type == "websocket.disconnect":
                self._shutdown_queues()
                return

            raw_bytes = message.get("bytes")
            raw_text = message.get("text")

            if raw_bytes:
                await self._handle_audio(raw_bytes)
            elif raw_text:
                await self._handle_control(raw_text)

    async def _handle_audio(self, pcm_data: bytes) -> None:
        event, utterance = self.vad.process_chunk(pcm_data)

        if event == "speech_start":
            if self.state == SessionState.SPEAKING:
                await self._barge_in()
            await self._set_state(SessionState.LISTENING)

        elif event == "speech_end":
            await self._set_state(SessionState.THINKING)
            await self.audio_queue.put(utterance)

    async def _handle_control(self, text: str) -> None:
        try:
            msg: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError:
            return
        if msg.get("type") == "interrupt":
            await self._barge_in()

    # ------------------------------------------------------------------
    # Stage 2: STT
    # ------------------------------------------------------------------

    async def _stt_worker(self) -> None:
        loop = asyncio.get_event_loop()
        while True:
            audio_bytes = await self.audio_queue.get()
            if audio_bytes is None:
                await self.text_queue.put(None)
                return

            # Clear any previous barge-in cancellation now that we have
            # new user audio to process.
            self._cancel.clear()

            text: str = await loop.run_in_executor(
                None, self.stt.transcribe, audio_bytes
            )
            if text and not self._cancel.is_set():
                await self._send_json(type="transcript", text=text, role="user")
                self.messages.append({"role": "user", "content": text})
                await self.text_queue.put(text)

    # ------------------------------------------------------------------
    # Stage 3: LLM streaming + sentence chunking
    # ------------------------------------------------------------------

    async def _llm_worker(self) -> None:
        while True:
            user_text = await self.text_queue.get()
            if user_text is None:
                await self.sentence_queue.put(None)
                return

            # Refresh system prompt so joke selection rotates each turn
            self.messages[0]["content"] = settings.get_system_prompt()

            try:
                await self._llm_generate(tools=_TOOLS)
            except Exception:
                logger.exception("LLM streaming error")
                await self._send_json(type="error", message="LLM error")
                await self._set_state(SessionState.IDLE)

    async def _llm_generate(
        self,
        tools: list[dict[str, Any]] | None = None,
    ) -> None:
        """Run one LLM generation, handling a single tool-call round if needed."""
        chunker = SentenceChunker()
        full_response = ""
        tool_calls: list[ToolCall] = []

        async for event in self.llm.stream_chat(self.messages, tools=tools):
            if self._cancel.is_set():
                return
            if event.token:
                full_response += event.token
                for sentence in chunker.add_token(event.token):
                    await self.sentence_queue.put(sentence)
            if event.tool_calls:
                tool_calls = event.tool_calls

        if self._cancel.is_set():
            return

        # --- Handle tool calls ---
        if tool_calls:
            tc = tool_calls[0]
            logger.info("Tool call: %s(%s)", tc.name, tc.arguments)

            if tc.name == "calculate":
                result = execute_calculate_tool(tc.arguments)
                logger.info("Calculate result: %s", result)

                # Append the assistant's tool-call message
                self.messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }],
                })
                # Append the tool result
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

                # Second LLM call (no tools) to produce the spoken answer
                await self._llm_generate(tools=None)
                return

        # --- Regular text response ---
        remaining = chunker.flush()
        if remaining:
            await self.sentence_queue.put(remaining)

        # Sentinel: end of this response
        await self.sentence_queue.put(None)

        if full_response:
            self.messages.append(
                {"role": "assistant", "content": full_response}
            )
            await self._send_json(
                type="transcript", text=full_response, role="assistant"
            )


    # ------------------------------------------------------------------
    # Stage 4: TTS
    # ------------------------------------------------------------------

    async def _tts_worker(self) -> None:
        loop = asyncio.get_event_loop()
        while True:
            sentence = await self.sentence_queue.get()
            if sentence is None:
                # Propagate end-of-response sentinel
                await self.tts_audio_queue.put(None)
                if self._done:
                    return
                continue

            if self._cancel.is_set():
                continue

            if self._grammar_tool is not None:
                try:
                    sentence = await loop.run_in_executor(
                        None, self._correct_grammar, sentence
                    )
                except Exception:
                    logger.debug("Grammar check failed, using original", exc_info=True)

            sentence = _EMOJI_RE.sub("", sentence).strip()
            sentence = _sanitize_for_tts(sentence)
            if not sentence or not any(c.isalpha() for c in sentence):
                continue

            try:
                audio_bytes: bytes = await loop.run_in_executor(
                    None, self.tts.synthesize, sentence
                )
            except Exception:
                logger.exception("TTS error for: %s", sentence[:50])
                continue

            if not self._cancel.is_set():
                await self.tts_audio_queue.put(audio_bytes)

    # ------------------------------------------------------------------
    # Stage 5: Send audio to client
    # ------------------------------------------------------------------

    async def _audio_send_loop(self) -> None:
        while True:
            audio_bytes = await self.tts_audio_queue.get()
            if audio_bytes is None:
                # All audio for this turn sent
                if self.state == SessionState.SPEAKING:
                    await self._set_state(SessionState.IDLE)
                if self._done:
                    return
                continue

            if self.state != SessionState.SPEAKING:
                await self._set_state(SessionState.SPEAKING)

            # Send in small chunks to allow barge-in between sends
            for i in range(0, len(audio_bytes), _WS_AUDIO_CHUNK):
                if self._cancel.is_set():
                    break
                chunk = audio_bytes[i : i + _WS_AUDIO_CHUNK]
                await self.ws.send_bytes(chunk)
                # Yield to event loop so barge-in can be processed
                await asyncio.sleep(0)

    # ------------------------------------------------------------------
    # Barge-in / cancellation
    # ------------------------------------------------------------------

    async def _barge_in(self) -> None:
        """Cancel the current response pipeline immediately."""
        logger.info("Barge-in triggered")
        self._cancel.set()

        # Drain all queues
        for q in (
            self.audio_queue,
            self.text_queue,
            self.sentence_queue,
            self.tts_audio_queue,
        ):
            while not q.empty():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    break

        self.vad.reset()
        # NOTE: do NOT clear _cancel here. It stays set so that workers
        # currently blocked in run_in_executor (TTS synthesis, etc.) will
        # see the cancellation when they return.  _cancel is cleared in
        # _stt_worker when new user audio arrives for processing.
        await self._set_state(SessionState.IDLE)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _correct_grammar(self, text: str) -> str:
        """Auto-correct French grammar using LanguageTool. Blocking."""
        import language_tool_python  # type: ignore[import-untyped]

        matches = self._grammar_tool.check(text)
        if matches:
            corrected = language_tool_python.utils.correct(text, matches)
            if corrected != text:
                logger.info("Grammar: %r -> %r", text, corrected)
            return corrected
        return text

    async def _set_state(self, new_state: SessionState) -> None:
        if new_state != self.state:
            self.state = new_state
            await self._send_json(type="state", state=new_state.value)

    async def _send_json(self, **kwargs: str | int) -> None:
        try:
            await self.ws.send_json(kwargs)
        except Exception:
            logger.debug("Failed to send JSON to client", exc_info=True)

    def _shutdown_queues(self) -> None:
        """Push None sentinels to unblock all workers and signal shutdown."""
        self._done = True
        for q in (
            self.audio_queue,
            self.text_queue,
            self.sentence_queue,
            self.tts_audio_queue,
        ):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass
