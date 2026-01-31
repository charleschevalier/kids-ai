import {renderHook, act} from '@testing-library/react-native';
import {useAudioPlayback} from '../../src/hooks/useAudioPlayback';

// The mock from __mocks__/react-native-audio-api.ts is auto-loaded
jest.mock('react-native-audio-api');

describe('useAudioPlayback', () => {
  it('initializes without error', () => {
    const {result} = renderHook(() => useAudioPlayback());
    expect(result.current.playChunk).toBeDefined();
    expect(result.current.stopPlayback).toBeDefined();
    expect(result.current.setSampleRate).toBeDefined();
  });

  it('setSampleRate updates the sample rate', () => {
    const {result} = renderHook(() => useAudioPlayback());
    // Should not throw
    act(() => {
      result.current.setSampleRate(22050);
    });
  });

  it('playChunk accepts an ArrayBuffer', () => {
    const {result} = renderHook(() => useAudioPlayback());

    act(() => {
      result.current.setSampleRate(22050);
    });

    const int16 = new Int16Array([0, 100, -100, 200]);
    act(() => {
      result.current.playChunk(int16.buffer);
    });
    // Should not throw
  });

  it('stopPlayback does not throw when no audio is playing', () => {
    const {result} = renderHook(() => useAudioPlayback());

    act(() => {
      result.current.stopPlayback();
    });
    // Should not throw
  });

  it('stopPlayback after playChunk does not throw', () => {
    const {result} = renderHook(() => useAudioPlayback());

    const int16 = new Int16Array([0, 100, -100, 200]);
    act(() => {
      result.current.playChunk(int16.buffer);
    });

    act(() => {
      result.current.stopPlayback();
    });
    // Should not throw
  });

  it('can play multiple chunks sequentially', () => {
    const {result} = renderHook(() => useAudioPlayback());

    const chunk1 = new Int16Array([100, 200, 300]);
    const chunk2 = new Int16Array([400, 500, 600]);

    act(() => {
      result.current.playChunk(chunk1.buffer);
      result.current.playChunk(chunk2.buffer);
    });
    // Should not throw
  });

  it('can play again after stopPlayback', () => {
    const {result} = renderHook(() => useAudioPlayback());

    const chunk = new Int16Array([100, 200]);
    act(() => {
      result.current.playChunk(chunk.buffer);
    });

    act(() => {
      result.current.stopPlayback();
    });

    // Should be able to play again (new source node created)
    act(() => {
      result.current.playChunk(chunk.buffer);
    });
    // Should not throw
  });
});
