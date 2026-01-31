import {useEffect, useRef} from 'react';
import {Platform, PermissionsAndroid} from 'react-native';
import {AudioRecorder} from 'react-native-audio-api';
import {CAPTURE_SAMPLE_RATE, CAPTURE_CHANNELS, CAPTURE_FRAME_SIZE} from '../config';
import {float32ToS16LE} from '../utils/pcm';

async function requestMicPermission(): Promise<boolean> {
  if (Platform.OS !== 'android') {
    return true;
  }
  const granted = await PermissionsAndroid.request(
    PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
  );
  return granted === PermissionsAndroid.RESULTS.GRANTED;
}

export function useAudioCapture(
  sendBinary: (data: ArrayBuffer) => void,
  isConnected: boolean,
) {
  const recorderRef = useRef<AudioRecorder | null>(null);
  const isRecordingRef = useRef(false);

  useEffect(() => {
    if (!isConnected) {
      if (recorderRef.current && isRecordingRef.current) {
        recorderRef.current.stop();
        isRecordingRef.current = false;
      }
      return;
    }

    let cancelled = false;

    async function startCapture() {
      const permitted = await requestMicPermission();
      if (!permitted || cancelled) {
        return;
      }

      const recorder = new AudioRecorder();
      recorderRef.current = recorder;

      recorder.onAudioReady(
        {
          sampleRate: CAPTURE_SAMPLE_RATE,
          bufferLength: CAPTURE_FRAME_SIZE,
          channelCount: CAPTURE_CHANNELS,
        },
        ({buffer}) => {
          const float32 = buffer.getChannelData(0);
          const s16le = float32ToS16LE(float32);
          sendBinary(s16le);
        },
      );

      const result = recorder.start();
      if (result.status === 'success') {
        isRecordingRef.current = true;
      }
    }

    startCapture();

    return () => {
      cancelled = true;
      if (recorderRef.current && isRecordingRef.current) {
        recorderRef.current.stop();
        isRecordingRef.current = false;
      }
      recorderRef.current = null;
    };
  }, [isConnected, sendBinary]);
}
