from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
import torch

# Number of audio chunks to keep before VAD triggers, so the onset of
# speech is not lost.  At 32 ms per chunk this gives ~300 ms of lookback.
_PRE_SPEECH_CHUNKS = 10


class VADProcessor:
    """Wraps Silero VAD. Accumulates PCM during speech,
    returns the complete utterance when speech ends."""

    def __init__(
        self,
        model: Any,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        min_silence_ms: int = 700,
        min_speech_ms: int = 250,
    ) -> None:
        self.model: Any = model
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_silence_samples = int(min_silence_ms * sample_rate / 1000)
        self.min_speech_samples = int(min_speech_ms * sample_rate / 1000)

        self.is_speaking = False
        self.speech_buffer = bytearray()
        self.silence_samples = 0
        self._pre_buffer: deque[bytes] = deque(maxlen=_PRE_SPEECH_CHUNKS)

        # Silero VAD internal state
        self.model.reset_states()

    def process_chunk(self, pcm_s16le: bytes) -> tuple[str, bytes | None]:
        """Process a chunk of 16-bit PCM audio (512 samples / 32ms at 16kHz).

        Returns one of:
            ("speech_start", None)      - speech just started
            ("speech_end", audio_bytes) - speech ended, full utterance returned
            ("speech_continue", None)   - still in speech
            ("silence", None)           - no speech detected
        """
        audio_f32 = np.frombuffer(pcm_s16le, dtype=np.int16).astype(np.float32) / 32768.0
        chunk_tensor = torch.from_numpy(audio_f32)  # type: ignore[no-untyped-call]

        confidence: float = self.model(chunk_tensor, self.sample_rate).item()
        is_speech = confidence >= self.threshold
        num_samples = len(audio_f32)

        if is_speech:
            self.silence_samples = 0

            if not self.is_speaking:
                # Speech just started — prepend recent silence chunks so the
                # onset of the word is not clipped.
                self.is_speaking = True
                self.speech_buffer = bytearray()
                for prev_chunk in self._pre_buffer:
                    self.speech_buffer.extend(prev_chunk)
                self._pre_buffer.clear()
                self.speech_buffer.extend(pcm_s16le)
                return ("speech_start", None)

            # Continuing speech
            self.speech_buffer.extend(pcm_s16le)
            return ("speech_continue", None)

        # Silence frame
        if not self.is_speaking:
            self._pre_buffer.append(pcm_s16le)
        if self.is_speaking:
            self.speech_buffer.extend(pcm_s16le)
            self.silence_samples += num_samples

            if self.silence_samples >= self.min_silence_samples:
                # Enough silence to consider speech ended
                self.is_speaking = False
                self.silence_samples = 0
                utterance = bytes(self.speech_buffer)
                self.speech_buffer = bytearray()

                # Check minimum speech length
                total_samples = len(utterance) // 2  # 16-bit = 2 bytes/sample
                if total_samples < self.min_speech_samples:
                    return ("silence", None)

                return ("speech_end", utterance)

            return ("speech_continue", None)

        return ("silence", None)

    def reset(self) -> None:
        """Reset all state. Call on barge-in or session reset."""
        self.model.reset_states()
        self.is_speaking = False
        self.speech_buffer = bytearray()
        self.silence_samples = 0
        self._pre_buffer.clear()
