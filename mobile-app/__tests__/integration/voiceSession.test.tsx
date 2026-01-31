import React from 'react';
import {Text} from 'react-native';
import {render, act} from '@testing-library/react-native';
import {VoiceSession, useSession} from '../../src/components/VoiceSession';

jest.mock('react-native-audio-api');
jest.mock('react-native-reanimated');

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];

  url: string;
  binaryType: string = '';
  readyState: number = 0;
  onopen: ((event: any) => void) | null = null;
  onclose: ((event: any) => void) | null = null;
  onmessage: ((event: any) => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  sent: any[] = [];

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: any) {
    this.sent.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
  }

  __simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.({});
  }

  __simulateMessage(data: any) {
    this.onmessage?.({data});
  }

  __simulateClose() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({});
  }
}

(globalThis as any).WebSocket = MockWebSocket;

// Test consumer component that shows session state
function StateDisplay() {
  const {state, transcripts, error} = useSession();
  return (
    <>
      <Text testID="state">{state}</Text>
      <Text testID="transcripts">{JSON.stringify(transcripts)}</Text>
      <Text testID="error">{error || ''}</Text>
    </>
  );
}

describe('VoiceSession integration', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
  });

  it('starts in DISCONNECTED state, transitions to IDLE on connect', async () => {
    const {getByTestId} = render(
      <VoiceSession>
        <StateDisplay />
      </VoiceSession>,
    );

    // Initially disconnected
    expect(getByTestId('state').props.children).toBe('DISCONNECTED');

    // Simulate WebSocket connection
    await act(async () => {
      MockWebSocket.instances[0].__simulateOpen();
    });

    expect(getByTestId('state').props.children).toBe('IDLE');
  });

  it('processes tts_config followed by state messages', async () => {
    const {getByTestId} = render(
      <VoiceSession>
        <StateDisplay />
      </VoiceSession>,
    );

    const ws = MockWebSocket.instances[0];

    await act(async () => {
      ws.__simulateOpen();
    });

    // Server sends tts_config
    await act(async () => {
      ws.__simulateMessage(
        JSON.stringify({
          type: 'tts_config',
          sample_rate: 22050,
          channels: 1,
          format: 's16le',
        }),
      );
    });

    // Server sends LISTENING state
    await act(async () => {
      ws.__simulateMessage(
        JSON.stringify({type: 'state', state: 'LISTENING'}),
      );
    });

    expect(getByTestId('state').props.children).toBe('LISTENING');

    // Server sends THINKING state
    await act(async () => {
      ws.__simulateMessage(
        JSON.stringify({type: 'state', state: 'THINKING'}),
      );
    });

    expect(getByTestId('state').props.children).toBe('THINKING');
  });

  it('stores transcripts from server messages', async () => {
    const {getByTestId} = render(
      <VoiceSession>
        <StateDisplay />
      </VoiceSession>,
    );

    const ws = MockWebSocket.instances[0];
    await act(async () => ws.__simulateOpen());

    await act(async () => {
      ws.__simulateMessage(
        JSON.stringify({type: 'transcript', text: 'Bonjour', role: 'user'}),
      );
    });

    const transcripts = JSON.parse(
      getByTestId('transcripts').props.children,
    );
    expect(transcripts).toHaveLength(1);
    expect(transcripts[0]).toEqual({text: 'Bonjour', role: 'user'});
  });

  it('handles binary audio messages without crashing', async () => {
    const {getByTestId} = render(
      <VoiceSession>
        <StateDisplay />
      </VoiceSession>,
    );

    const ws = MockWebSocket.instances[0];
    await act(async () => ws.__simulateOpen());

    // Send tts_config first
    await act(async () => {
      ws.__simulateMessage(
        JSON.stringify({
          type: 'tts_config',
          sample_rate: 22050,
          channels: 1,
          format: 's16le',
        }),
      );
    });

    // Send binary audio chunk
    const audioChunk = new Int16Array([100, 200, -100, -200]).buffer;
    await act(async () => {
      ws.__simulateMessage(audioChunk);
    });

    // Should not crash - state should still be valid
    expect(getByTestId('state').props.children).toBe('IDLE');
  });

  it('transitions back to DISCONNECTED on WebSocket close', async () => {
    jest.useFakeTimers();

    const {getByTestId} = render(
      <VoiceSession>
        <StateDisplay />
      </VoiceSession>,
    );

    const ws = MockWebSocket.instances[0];
    await act(async () => ws.__simulateOpen());

    expect(getByTestId('state').props.children).toBe('IDLE');

    await act(async () => {
      ws.__simulateClose();
    });

    expect(getByTestId('state').props.children).toBe('DISCONNECTED');

    jest.useRealTimers();
  });

  it('displays error from server error message', async () => {
    const {getByTestId} = render(
      <VoiceSession>
        <StateDisplay />
      </VoiceSession>,
    );

    const ws = MockWebSocket.instances[0];
    await act(async () => ws.__simulateOpen());

    await act(async () => {
      ws.__simulateMessage(
        JSON.stringify({type: 'error', message: 'STT failed'}),
      );
    });

    expect(getByTestId('error').props.children).toBe('STT failed');
  });

  it('full conversation flow: IDLE -> LISTENING -> THINKING -> SPEAKING -> IDLE', async () => {
    const {getByTestId} = render(
      <VoiceSession>
        <StateDisplay />
      </VoiceSession>,
    );

    const ws = MockWebSocket.instances[0];
    await act(async () => ws.__simulateOpen());

    // tts_config
    await act(async () => {
      ws.__simulateMessage(
        JSON.stringify({type: 'tts_config', sample_rate: 22050, channels: 1, format: 's16le'}),
      );
    });

    // User speaks -> LISTENING
    await act(async () => {
      ws.__simulateMessage(JSON.stringify({type: 'state', state: 'LISTENING'}));
    });
    expect(getByTestId('state').props.children).toBe('LISTENING');

    // Speech end -> THINKING
    await act(async () => {
      ws.__simulateMessage(JSON.stringify({type: 'state', state: 'THINKING'}));
    });
    expect(getByTestId('state').props.children).toBe('THINKING');

    // User transcript
    await act(async () => {
      ws.__simulateMessage(
        JSON.stringify({type: 'transcript', text: 'Raconte-moi une histoire', role: 'user'}),
      );
    });

    // Server starts speaking -> SPEAKING
    await act(async () => {
      ws.__simulateMessage(JSON.stringify({type: 'state', state: 'SPEAKING'}));
    });
    expect(getByTestId('state').props.children).toBe('SPEAKING');

    // Binary audio arrives
    const audio = new Int16Array(512).buffer;
    await act(async () => {
      ws.__simulateMessage(audio);
    });

    // Speaking done -> IDLE
    await act(async () => {
      ws.__simulateMessage(JSON.stringify({type: 'state', state: 'IDLE'}));
    });
    expect(getByTestId('state').props.children).toBe('IDLE');

    // Assistant transcript
    await act(async () => {
      ws.__simulateMessage(
        JSON.stringify({type: 'transcript', text: 'Il était une fois...', role: 'assistant'}),
      );
    });

    const transcripts = JSON.parse(getByTestId('transcripts').props.children);
    expect(transcripts).toHaveLength(2);
    expect(transcripts[0].role).toBe('user');
    expect(transcripts[1].role).toBe('assistant');
  });
});
