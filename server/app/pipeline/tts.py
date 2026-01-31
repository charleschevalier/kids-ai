from __future__ import annotations

from typing import Any

from piper import PiperVoice  # type: ignore[import-untyped]


class TTSProcessor:
    """Wraps Piper TTS. Synthesizes text to raw PCM audio bytes."""

    def __init__(
        self,
        voice: PiperVoice,
        sentence_silence: float = 0.3,
    ) -> None:
        self.voice: Any = voice
        self.sample_rate: int = voice.config.sample_rate  # typically 22050
        self.sentence_silence = sentence_silence

    def synthesize(self, text: str) -> bytes:
        """Synthesize text to raw s16le PCM bytes.

        This is BLOCKING — run in an executor.
        """
        audio_chunks: list[bytes] = []
        for chunk in self.voice.synthesize_stream_raw(
            text, sentence_silence=self.sentence_silence
        ):
            audio_chunks.append(chunk)
        return b"".join(audio_chunks)
