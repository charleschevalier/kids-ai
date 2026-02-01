from __future__ import annotations

from typing import Any

import numpy as np


class TTSProcessor:
    """Wraps Chatterbox TTS French. Synthesizes text to raw PCM audio bytes."""

    def __init__(
        self,
        model: Any,
        speaker_wav: str | None = None,
        sentence_silence: float = 0.3,
        exaggeration: float = 0.5,
        temperature: float = 0.6,
        cfg_weight: float = 0.3,
    ) -> None:
        self.model = model
        self.speaker_wav = speaker_wav
        self.sample_rate: int = model.sr
        self.sentence_silence = sentence_silence
        self._silence_samples = int(self.sample_rate * sentence_silence)
        self._gen_kwargs = {
            "exaggeration": exaggeration,
            "temperature": temperature,
            "cfg_weight": cfg_weight,
        }

    def synthesize(self, text: str) -> bytes:
        """Synthesize text to raw s16le PCM bytes.

        This is BLOCKING — run in an executor.
        """
        wav = self.model.generate(
            text=text,
            audio_prompt_path=self.speaker_wav,
            **self._gen_kwargs,
        )
        audio_np = wav.squeeze().cpu().numpy()
        pcm = (np.clip(audio_np, -1.0, 1.0) * 32767).astype(np.int16)
        audio = pcm.tobytes()
        if self._silence_samples > 0:
            audio += b"\x00\x00" * self._silence_samples
        return audio
