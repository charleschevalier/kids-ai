export class AudioRecorder {
  private _onAudioReadyCb: ((event: any) => void) | null = null;
  private _recording = false;

  onAudioReady(
    _options: {sampleRate: number; bufferLength: number; channelCount: number},
    callback: (event: any) => void,
  ) {
    this._onAudioReadyCb = callback;
    return {status: 'success' as const};
  }

  clearOnAudioReady() {
    this._onAudioReadyCb = null;
  }

  onError(_callback: (error: any) => void) {}
  clearOnError() {}

  start() {
    this._recording = true;
    return {status: 'success' as const, path: '/mock/path'};
  }

  stop() {
    this._recording = false;
    return {status: 'success' as const, path: '/mock/path', size: 0, duration: 0};
  }

  pause() {}
  resume() {}

  isRecording() {
    return this._recording;
  }

  // Test helper: simulate audio data arriving
  __simulateAudioReady(float32Data: Float32Array) {
    if (this._onAudioReadyCb) {
      this._onAudioReadyCb({
        buffer: {
          getChannelData: () => float32Data,
          length: float32Data.length,
          numberOfChannels: 1,
          sampleRate: 16000,
          duration: float32Data.length / 16000,
        },
        numFrames: float32Data.length,
        when: 0,
      });
    }
  }
}

const mockSourceNode = {
  connect: jest.fn(),
  disconnect: jest.fn(),
  start: jest.fn(),
  stop: jest.fn(),
  pause: jest.fn(),
  enqueueBuffer: jest.fn().mockReturnValue('buffer-id'),
  dequeueBuffer: jest.fn(),
  clearBuffers: jest.fn(),
  buffer: null,
  onEnded: null,
};

const mockAudioBuffer = {
  getChannelData: jest.fn().mockReturnValue(new Float32Array(512)),
  copyToChannel: jest.fn(),
  copyFromChannel: jest.fn(),
  length: 512,
  duration: 512 / 22050,
  sampleRate: 22050,
  numberOfChannels: 1,
};

export class AudioContext {
  sampleRate = 44100;
  currentTime = 0;
  state = 'running';

  createBufferSource() {
    return {...mockSourceNode};
  }

  createBufferQueueSource() {
    return {...mockSourceNode};
  }

  createBuffer(channels: number, length: number, sampleRate: number) {
    return {
      ...mockAudioBuffer,
      length,
      sampleRate,
      numberOfChannels: channels,
      duration: length / sampleRate,
      getChannelData: jest.fn().mockReturnValue(new Float32Array(length)),
      copyToChannel: jest.fn(),
    };
  }

  createGain() {
    return {
      connect: jest.fn(),
      disconnect: jest.fn(),
      gain: {value: 1, setValueAtTime: jest.fn()},
    };
  }

  get destination() {
    return {maxChannelCount: 2};
  }

  close() {
    return Promise.resolve();
  }

  resume() {
    return Promise.resolve(true);
  }

  suspend() {
    return Promise.resolve(true);
  }
}

export class AudioBufferQueueSourceNode {
  connect = jest.fn();
  disconnect = jest.fn();
  start = jest.fn();
  stop = jest.fn();
  pause = jest.fn();
  enqueueBuffer = jest.fn().mockReturnValue('buffer-id');
  dequeueBuffer = jest.fn();
  clearBuffers = jest.fn();
}

export const AudioManager = {
  requestRecordingPermissions: jest.fn().mockResolvedValue(true),
};
