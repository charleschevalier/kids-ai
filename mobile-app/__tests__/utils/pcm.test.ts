import {float32ToS16LE, s16LEToFloat32} from '../../src/utils/pcm';

describe('float32ToS16LE', () => {
  it('converts silence (zeros) correctly', () => {
    const input = new Float32Array([0, 0, 0, 0]);
    const output = new Int16Array(float32ToS16LE(input));
    expect(Array.from(output)).toEqual([0, 0, 0, 0]);
  });

  it('converts max positive value', () => {
    const input = new Float32Array([1.0]);
    const output = new Int16Array(float32ToS16LE(input));
    expect(output[0]).toBe(32767); // 0x7FFF
  });

  it('converts max negative value', () => {
    const input = new Float32Array([-1.0]);
    const output = new Int16Array(float32ToS16LE(input));
    expect(output[0]).toBe(-32768); // -0x8000
  });

  it('clamps values above 1.0', () => {
    const input = new Float32Array([1.5]);
    const output = new Int16Array(float32ToS16LE(input));
    expect(output[0]).toBe(32767);
  });

  it('clamps values below -1.0', () => {
    const input = new Float32Array([-1.5]);
    const output = new Int16Array(float32ToS16LE(input));
    expect(output[0]).toBe(-32768);
  });

  it('handles empty array', () => {
    const input = new Float32Array([]);
    const output = new Int16Array(float32ToS16LE(input));
    expect(output.length).toBe(0);
  });

  it('returns a buffer with correct byte length', () => {
    const input = new Float32Array([0.5, -0.5]);
    const result = float32ToS16LE(input);
    expect(result.byteLength).toBe(4); // 2 samples * 2 bytes
    // Verify it can be wrapped in Int16Array
    const view = new Int16Array(result);
    expect(view.length).toBe(2);
  });
});

describe('s16LEToFloat32', () => {
  it('converts silence (zeros) correctly', () => {
    const int16 = new Int16Array([0, 0, 0, 0]);
    const output = s16LEToFloat32(int16.buffer);
    expect(Array.from(output)).toEqual([0, 0, 0, 0]);
  });

  it('converts max positive value', () => {
    const int16 = new Int16Array([32767]);
    const output = s16LEToFloat32(int16.buffer);
    expect(output[0]).toBeCloseTo(1.0, 3);
  });

  it('converts max negative value', () => {
    const int16 = new Int16Array([-32768]);
    const output = s16LEToFloat32(int16.buffer);
    expect(output[0]).toBe(-1.0);
  });

  it('handles empty buffer', () => {
    const int16 = new Int16Array([]);
    const output = s16LEToFloat32(int16.buffer);
    expect(output.length).toBe(0);
  });

  it('returns a Float32Array', () => {
    const int16 = new Int16Array([100, -100]);
    const output = s16LEToFloat32(int16.buffer);
    expect(output).toBeInstanceOf(Float32Array);
    expect(output.length).toBe(2);
  });
});

describe('roundtrip conversion', () => {
  it('preserves values within s16le precision', () => {
    // Start with s16le values, convert to float32, then back
    const original = new Int16Array([0, 16384, -16384, 32767, -32768]);
    const float32 = s16LEToFloat32(original.buffer);
    const roundtripped = new Int16Array(float32ToS16LE(float32));

    for (let i = 0; i < original.length; i++) {
      // Allow +-1 for rounding
      expect(Math.abs(roundtripped[i] - original[i])).toBeLessThanOrEqual(1);
    }
  });
});
