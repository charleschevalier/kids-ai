import {useCallback, useEffect, useRef} from 'react';
import {RECONNECT_BASE_DELAY_MS, RECONNECT_MAX_DELAY_MS} from '../config';

type TextMessageHandler = (msg: any) => void;
type BinaryMessageHandler = (data: ArrayBuffer) => void;

export function useWebSocket(
  url: string,
  onTextMessage: TextMessageHandler,
  onBinaryMessage: BinaryMessageHandler,
  onConnected: () => void,
  onDisconnected: () => void,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelay = useRef(RECONNECT_BASE_DELAY_MS);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) {
      return;
    }

    const ws = new WebSocket(url);
    // RN WebSocket supports binaryType but the type definition is incomplete
    (ws as any).binaryType = 'arraybuffer';

    ws.onopen = () => {
      reconnectDelay.current = RECONNECT_BASE_DELAY_MS;
      onConnected();
    };

    ws.onmessage = (event) => {
      const {data} = event;
      if (data instanceof ArrayBuffer) {
        onBinaryMessage(data);
      } else if (typeof data === 'string') {
        try {
          const msg = JSON.parse(data);
          onTextMessage(msg);
        } catch {
          // Ignore malformed JSON
        }
      }
    };

    ws.onclose = () => {
      onDisconnected();
      if (mountedRef.current) {
        reconnectTimer.current = setTimeout(() => {
          reconnectDelay.current = Math.min(
            reconnectDelay.current * 2,
            RECONNECT_MAX_DELAY_MS,
          );
          connect();
        }, reconnectDelay.current);
      }
    };

    ws.onerror = () => {
      // onclose will fire after onerror, triggering reconnect
    };

    wsRef.current = ws;
  }, [url, onTextMessage, onBinaryMessage, onConnected, onDisconnected]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on cleanup
        wsRef.current.close();
      }
    };
  }, [connect]);

  const sendBinary = useCallback((data: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  const sendJSON = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const isConnected =
    wsRef.current?.readyState === WebSocket.OPEN;

  return {sendBinary, sendJSON, isConnected};
}
