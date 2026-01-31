import {renderHook, act} from '@testing-library/react-native';
import {useSessionState} from '../../src/hooks/useSessionState';

describe('useSessionState', () => {
  it('starts with DISCONNECTED state', () => {
    const {result} = renderHook(() => useSessionState());
    expect(result.current.state).toBe('DISCONNECTED');
  });

  it('starts with empty transcripts', () => {
    const {result} = renderHook(() => useSessionState());
    expect(result.current.transcripts).toEqual([]);
  });

  it('starts with null sampleRate', () => {
    const {result} = renderHook(() => useSessionState());
    expect(result.current.sampleRate).toBeNull();
  });

  it('starts with null error', () => {
    const {result} = renderHook(() => useSessionState());
    expect(result.current.error).toBeNull();
  });

  it('transitions to correct state on state message', () => {
    const {result} = renderHook(() => useSessionState());

    act(() => {
      result.current.handleMessage({type: 'state', state: 'IDLE'});
    });
    expect(result.current.state).toBe('IDLE');

    act(() => {
      result.current.handleMessage({type: 'state', state: 'LISTENING'});
    });
    expect(result.current.state).toBe('LISTENING');

    act(() => {
      result.current.handleMessage({type: 'state', state: 'THINKING'});
    });
    expect(result.current.state).toBe('THINKING');

    act(() => {
      result.current.handleMessage({type: 'state', state: 'SPEAKING'});
    });
    expect(result.current.state).toBe('SPEAKING');
  });

  it('stores transcripts from transcript messages', () => {
    const {result} = renderHook(() => useSessionState());

    act(() => {
      result.current.handleMessage({
        type: 'transcript',
        text: 'Bonjour',
        role: 'user',
      });
    });
    expect(result.current.transcripts).toEqual([
      {text: 'Bonjour', role: 'user'},
    ]);

    act(() => {
      result.current.handleMessage({
        type: 'transcript',
        text: 'Salut!',
        role: 'assistant',
      });
    });
    expect(result.current.transcripts).toHaveLength(2);
    expect(result.current.transcripts[1]).toEqual({
      text: 'Salut!',
      role: 'assistant',
    });
  });

  it('stores sample rate from tts_config message', () => {
    const {result} = renderHook(() => useSessionState());

    act(() => {
      result.current.handleMessage({
        type: 'tts_config',
        sample_rate: 22050,
        channels: 1,
        format: 's16le',
      });
    });
    expect(result.current.sampleRate).toBe(22050);
  });

  it('stores error from error message', () => {
    const {result} = renderHook(() => useSessionState());

    act(() => {
      result.current.handleMessage({
        type: 'error',
        message: 'Something went wrong',
      });
    });
    expect(result.current.error).toBe('Something went wrong');
  });

  it('setDisconnected sets state to DISCONNECTED', () => {
    const {result} = renderHook(() => useSessionState());

    act(() => {
      result.current.handleMessage({type: 'state', state: 'IDLE'});
    });
    expect(result.current.state).toBe('IDLE');

    act(() => {
      result.current.setDisconnected();
    });
    expect(result.current.state).toBe('DISCONNECTED');
  });

  it('setConnected sets state to IDLE', () => {
    const {result} = renderHook(() => useSessionState());

    expect(result.current.state).toBe('DISCONNECTED');

    act(() => {
      result.current.setConnected();
    });
    expect(result.current.state).toBe('IDLE');
  });
});
