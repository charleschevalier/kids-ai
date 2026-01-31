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


def _load_piper_voice() -> Any:
    """Load Piper TTS voice."""
    from piper import PiperVoice  # type: ignore[import-untyped]

    logger.info("Loading Piper voice %s...", settings.piper_model)
    voice: Any = PiperVoice.load(settings.piper_model)
    logger.info("Piper voice loaded (sample_rate=%d)", voice.config.sample_rate)
    return voice


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    shared = SharedModels(
        vad_model=_load_vad_model(),
        whisper_model=_load_whisper_model(),
        piper_voice=_load_piper_voice(),
    )
    app.state.shared = shared
    logger.info("All models loaded. Server ready.")
    yield
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
