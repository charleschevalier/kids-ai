from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.config import settings
from app.session import Session, SharedModels

logger = logging.getLogger(__name__)


def _load_vad_model() -> Any:
    """Load Silero VAD model (ONNX, CPU)."""
    from silero_vad import load_silero_vad  # type: ignore[import-untyped]

    logger.info("Loading Silero VAD model...")
    result = cast(Any, load_silero_vad(onnx=True))  # pyright: ignore[reportUnknownVariableType]
    logger.info("Silero VAD loaded")
    return result


def _load_whisper_model() -> Any:
    """Load faster-whisper model."""
    from faster_whisper import WhisperModel  # type: ignore[import-untyped]

    logger.info(
        "Loading Whisper model %s on %s...",
        settings.whisper_model,
        settings.whisper_device,
    )
    model: Any = WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    logger.info("Whisper model loaded")
    return model


def _load_tts_model() -> Any:
    """Load Chatterbox TTS with French fine-tuned checkpoint."""
    from chatterbox.tts import ChatterboxTTS  # type: ignore[import-untyped]
    from huggingface_hub import hf_hub_download  # type: ignore[import-untyped]
    from safetensors.torch import load_file  # type: ignore[import-untyped]

    device = settings.tts_device
    logger.info("Loading Chatterbox TTS on %s...", device)
    model: Any = ChatterboxTTS.from_pretrained(device=device)

    # Load French fine-tuned checkpoint
    checkpoint_path = hf_hub_download(
        repo_id="Thomcles/Chatterbox-TTS-French",
        filename="t3_cfg.safetensors",
    )
    t3_state = load_file(checkpoint_path, device="cpu")
    model.t3.load_state_dict(t3_state)

    logger.info("Chatterbox TTS French loaded")
    return model


def _load_grammar_tool() -> Any:
    """Load LanguageTool for French grammar correction."""
    import language_tool_python  # type: ignore[import-untyped]

    logger.info("Loading LanguageTool (French)...")
    tool: Any = language_tool_python.LanguageTool("fr")
    logger.info("LanguageTool loaded")
    return tool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    grammar_tool = _load_grammar_tool()
    shared = SharedModels(
        vad_model=_load_vad_model(),
        whisper_model=_load_whisper_model(),
        tts_model=_load_tts_model(),
        grammar_tool=grammar_tool,
    )
    app.state.shared = shared
    logger.info("All models loaded. Server ready.")
    yield
    grammar_tool.close()
    logger.info("Shutting down.")


app = FastAPI(lifespan=lifespan)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    logger.info("Client connected: %s", ws.client)
    shared: SharedModels = ws.app.state.shared  # type: ignore[union-attr]
    session = Session(ws, shared)
    try:
        await session.run()
    except WebSocketDisconnect:
        logger.info("Client disconnected: %s", ws.client)
    except Exception:
        logger.exception("Session error")
    finally:
        await session.cleanup()
