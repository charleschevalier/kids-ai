import {useCallback, useState} from 'react';

export type SessionState =
  | 'IDLE'
  | 'LISTENING'
  | 'THINKING'
  | 'SPEAKING'
  | 'DISCONNECTED';

export type Transcript = {
  text: string;
  role: 'user' | 'assistant';
};

export type ServerMessage =
  | {type: 'tts_config'; sample_rate: number; channels: number; format: string}
  | {type: 'state'; state: 'IDLE' | 'LISTENING' | 'THINKING' | 'SPEAKING'}
  | {type: 'transcript'; text: string; role: 'user' | 'assistant'}
  | {type: 'error'; message: string};

export function useSessionState() {
  const [state, setState] = useState<SessionState>('DISCONNECTED');
  const [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const [sampleRate, setSampleRate] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case 'state':
        setState(msg.state);
        break;
      case 'transcript':
        setTranscripts(prev => [...prev, {text: msg.text, role: msg.role}]);
        break;
      case 'tts_config':
        setSampleRate(msg.sample_rate);
        break;
      case 'error':
        setError(msg.message);
        break;
    }
  }, []);

  const setDisconnected = useCallback(() => {
    setState('DISCONNECTED');
  }, []);

  const setConnected = useCallback(() => {
    setState('IDLE');
  }, []);

  return {
    state,
    transcripts,
    sampleRate,
    error,
    handleMessage,
    setDisconnected,
    setConnected,
  };
}
