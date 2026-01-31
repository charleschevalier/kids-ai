import {renderHook, act} from '@testing-library/react-native';
import {useWebSocket} from '../../src/hooks/useWebSocket';

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];

  url: string;
  binaryType: string = '';
  readyState: number = 0; // CONNECTING
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

  // Test helpers
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

describe('useWebSocket', () => {
  const mockOnText = jest.fn();
  const mockOnBinary = jest.fn();
  const mockOnConnected = jest.fn();
  const mockOnDisconnected = jest.fn();

  beforeEach(() => {
    jest.useFakeTimers();
    MockWebSocket.instances = [];
    mockOnText.mockClear();
    mockOnBinary.mockClear();
    mockOnConnected.mockClear();
    mockOnDisconnected.mockClear();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('connects to the given URL', () => {
    renderHook(() =>
      useWebSocket(
        'ws://test:8765/ws',
        mockOnText,
        mockOnBinary,
        mockOnConnected,
        mockOnDisconnected,
      ),
    );

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toBe('ws://test:8765/ws');
  });

  it('sets binaryType to arraybuffer', () => {
    renderHook(() =>
      useWebSocket(
        'ws://test:8765/ws',
        mockOnText,
        mockOnBinary,
        mockOnConnected,
        mockOnDisconnected,
      ),
    );

    expect(MockWebSocket.instances[0].binaryType).toBe('arraybuffer');
  });

  it('calls onConnected when WebSocket opens', () => {
    renderHook(() =>
      useWebSocket(
        'ws://test:8765/ws',
        mockOnText,
        mockOnBinary,
        mockOnConnected,
        mockOnDisconnected,
      ),
    );

    act(() => {
      MockWebSocket.instances[0].__simulateOpen();
    });

    expect(mockOnConnected).toHaveBeenCalledTimes(1);
  });

  it('dispatches JSON text messages to onTextMessage', () => {
    renderHook(() =>
      useWebSocket(
        'ws://test:8765/ws',
        mockOnText,
        mockOnBinary,
        mockOnConnected,
        mockOnDisconnected,
      ),
    );

    const ws = MockWebSocket.instances[0];
    act(() => ws.__simulateOpen());

    const msg = {type: 'state', state: 'IDLE'};
    act(() => ws.__simulateMessage(JSON.stringify(msg)));

    expect(mockOnText).toHaveBeenCalledWith(msg);
  });

  it('dispatches binary messages to onBinaryMessage', () => {
    renderHook(() =>
      useWebSocket(
        'ws://test:8765/ws',
        mockOnText,
        mockOnBinary,
        mockOnConnected,
        mockOnDisconnected,
      ),
    );

    const ws = MockWebSocket.instances[0];
    act(() => ws.__simulateOpen());

    const buffer = new ArrayBuffer(1024);
    act(() => ws.__simulateMessage(buffer));

    expect(mockOnBinary).toHaveBeenCalledWith(buffer);
  });

  it('ignores malformed JSON text messages', () => {
    renderHook(() =>
      useWebSocket(
        'ws://test:8765/ws',
        mockOnText,
        mockOnBinary,
        mockOnConnected,
        mockOnDisconnected,
      ),
    );

    const ws = MockWebSocket.instances[0];
    act(() => ws.__simulateOpen());
    act(() => ws.__simulateMessage('not valid json'));

    expect(mockOnText).not.toHaveBeenCalled();
  });

  it('sendBinary sends data when connected', () => {
    const {result} = renderHook(() =>
      useWebSocket(
        'ws://test:8765/ws',
        mockOnText,
        mockOnBinary,
        mockOnConnected,
        mockOnDisconnected,
      ),
    );

    const ws = MockWebSocket.instances[0];
    act(() => ws.__simulateOpen());

    const data = new ArrayBuffer(512);
    act(() => result.current.sendBinary(data));

    expect(ws.sent).toHaveLength(1);
    expect(ws.sent[0]).toBe(data);
  });

  it('sendJSON sends stringified JSON when connected', () => {
    const {result} = renderHook(() =>
      useWebSocket(
        'ws://test:8765/ws',
        mockOnText,
        mockOnBinary,
        mockOnConnected,
        mockOnDisconnected,
      ),
    );

    const ws = MockWebSocket.instances[0];
    act(() => ws.__simulateOpen());

    const msg = {type: 'interrupt'};
    act(() => result.current.sendJSON(msg));

    expect(ws.sent).toHaveLength(1);
    expect(ws.sent[0]).toBe(JSON.stringify(msg));
  });

  it('calls onDisconnected and reconnects on close', () => {
    renderHook(() =>
      useWebSocket(
        'ws://test:8765/ws',
        mockOnText,
        mockOnBinary,
        mockOnConnected,
        mockOnDisconnected,
      ),
    );

    expect(MockWebSocket.instances).toHaveLength(1);

    act(() => {
      MockWebSocket.instances[0].__simulateClose();
    });

    expect(mockOnDisconnected).toHaveBeenCalledTimes(1);

    // After reconnect delay, a new WebSocket should be created
    act(() => {
      jest.advanceTimersByTime(1500);
    });

    expect(MockWebSocket.instances).toHaveLength(2);
  });
});
