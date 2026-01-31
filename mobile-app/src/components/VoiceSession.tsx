import React, {createContext, useCallback, useContext} from 'react';
import {WS_URL} from '../config';
import {useWebSocket} from '../hooks/useWebSocket';
import {useSessionState, SessionState, Transcript, ServerMessage} from '../hooks/useSessionState';
import {useAudioCapture} from '../hooks/useAudioCapture';
import {useAudioPlayback} from '../hooks/useAudioPlayback';

type SessionContextType = {
  state: SessionState;
  transcripts: Transcript[];
  error: string | null;
};

const SessionContext = createContext<SessionContextType>({
  state: 'DISCONNECTED',
  transcripts: [],
  error: null,
});

export function useSession() {
  return useContext(SessionContext);
}

export function VoiceSession({children}: {children: React.ReactNode}) {
  const {
    state,
    transcripts,
    sampleRate,
    error,
    handleMessage,
    setDisconnected,
    setConnected,
  } = useSessionState();

  const {setSampleRate, playChunk, stopPlayback} = useAudioPlayback();

  const onTextMessage = useCallback(
    (msg: ServerMessage) => {
      handleMessage(msg);

      if (msg.type === 'tts_config') {
        setSampleRate(msg.sample_rate);
      }
      if (msg.type === 'state' && msg.state === 'LISTENING') {
        stopPlayback();
      }
    },
    [handleMessage, setSampleRate, stopPlayback],
  );

  const onBinaryMessage = useCallback(
    (data: ArrayBuffer) => {
      playChunk(data);
    },
    [playChunk],
  );

  const {sendBinary, isConnected} = useWebSocket(
    WS_URL,
    onTextMessage,
    onBinaryMessage,
    setConnected,
    setDisconnected,
  );

  useAudioCapture(sendBinary, isConnected);

  return (
    <SessionContext.Provider value={{state, transcripts, error}}>
      {children}
    </SessionContext.Provider>
  );
}
