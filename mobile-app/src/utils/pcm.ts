/**
 * Convert Float32Array [-1.0, 1.0] to s16le ArrayBuffer.
 * Used for sending mic audio to server.
 */
export function float32ToS16LE(float32: Float32Array): ArrayBuffer {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16.buffer;
}

/**
 * Convert s16le ArrayBuffer to Float32Array [-1.0, 1.0].
 * Used for playing TTS audio from server.
 */
export function s16LEToFloat32(s16le: ArrayBuffer): Float32Array {
  const int16 = new Int16Array(s16le);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i] / 32768.0;
  }
  return float32;
}
