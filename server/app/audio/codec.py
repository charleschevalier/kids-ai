from __future__ import annotations

import numpy as np


def pcm_s16le_to_float32(pcm_bytes: bytes) -> np.ndarray:
    """Convert raw 16-bit signed little-endian PCM to float32 in [-1.0, 1.0]."""
    return np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0


def float32_to_pcm_s16le(audio: np.ndarray) -> bytes:
    """Convert float32 [-1.0, 1.0] to raw 16-bit signed little-endian PCM."""
    return (audio * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
