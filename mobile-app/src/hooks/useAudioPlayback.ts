import {useCallback, useEffect, useRef} from 'react';
import {AudioContext, AudioBufferQueueSourceNode} from 'react-native-audio-api';
import {DEFAULT_PLAYBACK_SAMPLE_RATE} from '../config';
import {s16LEToFloat32} from '../utils/pcm';

export function useAudioPlayback() {
  const contextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<AudioBufferQueueSourceNode | null>(null);
  const sampleRateRef = useRef(DEFAULT_PLAYBACK_SAMPLE_RATE);
  const startedRef = useRef(false);

  useEffect(() => {
    const ctx = new AudioContext();
    contextRef.current = ctx;

    return () => {
      if (sourceRef.current) {
        try {
          sourceRef.current.stop();
        } catch {
          // already stopped
        }
        sourceRef.current.disconnect();
      }
      sourceRef.current = null;
      contextRef.current = null;
      ctx.close();
    };
  }, []);

  const ensureSource = useCallback(() => {
    const ctx = contextRef.current;
    if (!ctx) {
      return null;
    }

    if (!sourceRef.current) {
      const source = ctx.createBufferQueueSource();
      source.connect(ctx.destination);
      sourceRef.current = source;
      startedRef.current = false;
    }

    return sourceRef.current;
  }, []);

  const setSampleRate = useCallback((rate: number) => {
    sampleRateRef.current = rate;
  }, []);

  const playChunk = useCallback(
    (data: ArrayBuffer) => {
      const source = ensureSource();
      const ctx = contextRef.current;
      if (!source || !ctx) {
        return;
      }

      const float32 = s16LEToFloat32(data);
      const numSamples = float32.length;
      const audioBuffer = ctx.createBuffer(
        1,
        numSamples,
        sampleRateRef.current,
      );
      audioBuffer.copyToChannel(float32, 0);
      source.enqueueBuffer(audioBuffer);

      if (!startedRef.current) {
        source.start();
        startedRef.current = true;
      }
    },
    [ensureSource],
  );

  const stopPlayback = useCallback(() => {
    if (sourceRef.current) {
      try {
        sourceRef.current.stop();
      } catch {
        // already stopped
      }
      sourceRef.current.clearBuffers();
      sourceRef.current.disconnect();
      sourceRef.current = null;
      startedRef.current = false;
    }
  }, []);

  return {setSampleRate, playChunk, stopPlayback};
}
