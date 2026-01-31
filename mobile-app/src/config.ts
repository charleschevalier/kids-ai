// Server connection
export const WS_URL = 'ws://192.168.1.100:8765/ws';

// Audio capture settings (must match server expectations)
export const CAPTURE_SAMPLE_RATE = 16000;
export const CAPTURE_CHANNELS = 1;
export const CAPTURE_FRAME_SIZE = 512; // samples per frame
export const CAPTURE_BUFFER_BYTES = CAPTURE_FRAME_SIZE * 2; // 1024 bytes (s16le)

// Audio playback defaults (overridden by server tts_config)
export const DEFAULT_PLAYBACK_SAMPLE_RATE = 22050;

// WebSocket reconnect
export const RECONNECT_BASE_DELAY_MS = 1000;
export const RECONNECT_MAX_DELAY_MS = 10000;
