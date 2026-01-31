from __future__ import annotations

from typing import Any

import numpy as np
from faster_whisper import WhisperModel  # type: ignore[import-untyped]


class STTProcessor:
    """Wraps faster-whisper. Transcribes complete VAD-segmented utterances."""

    def __init__(
        self,
        model: WhisperModel,
        language: str = "fr",
        beam_size: int = 5,
    ) -> None:
        self.model: Any = model
        self.language = language
        self.beam_size = beam_size

    def transcribe(self, pcm_s16le: bytes) -> str:
        """Transcribe raw 16kHz s16le PCM bytes to text.

        This is BLOCKING — run in an executor.
        """
        audio = np.frombuffer(pcm_s16le, dtype=np.int16).astype(np.float32) / 32768.0

        segments, _info = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=self.beam_size,
            vad_filter=False,  # We already did VAD upstream
            without_timestamps=True,
        )

        text: str = " ".join(seg.text for seg in segments).strip()
        return text
