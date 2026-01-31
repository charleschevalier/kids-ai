import numpy as np

from app.audio.codec import float32_to_pcm_s16le, pcm_s16le_to_float32


def test_roundtrip():
    original = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
    pcm = float32_to_pcm_s16le(original)
    recovered = pcm_s16le_to_float32(pcm)
    np.testing.assert_allclose(recovered, original, atol=1 / 32768)


def test_silence():
    silence = np.zeros(160, dtype=np.float32)
    pcm = float32_to_pcm_s16le(silence)
    assert len(pcm) == 320  # 160 samples * 2 bytes
    recovered = pcm_s16le_to_float32(pcm)
    np.testing.assert_array_equal(recovered, silence)


def test_pcm_byte_length():
    pcm = float32_to_pcm_s16le(np.array([0.1, -0.2, 0.3], dtype=np.float32))
    assert len(pcm) == 6  # 3 samples * 2 bytes
