# Kids AI - Voice Assistant for Children

A low-latency, French-speaking voice assistant designed for children. The server handles all heavy processing (VAD, STT, LLM, TTS) and exposes a WebSocket API. The Android client captures mic audio, streams it over WebSocket, and plays back TTS responses — all behind a full-screen animated robot face.

## Architecture

```
Android app (React Native)       Server (Python)
┌──────────────┐    WebSocket    ┌─────────────────────────────┐
│ Mic capture  │───── PCM ──────>│ VAD (Silero, CPU)           │
│              │                 │   ↓                         │
│ Robot face   │                 │ STT (faster-whisper, GPU)   │
│ (animated)   │                 │   ↓                         │
│              │                 │ LLM (llama.cpp, GPU)        │
│              │                 │   ↓                         │
│              │                 │ Sentence chunker            │
│              │                 │   ↓                         │
│ Audio play   │<──── PCM ──────│ TTS (Piper, CPU)            │
└──────────────┘                 └─────────────────────────────┘
```

The client streams mic audio continuously over WebSocket. The server detects speech (VAD), transcribes it (STT), generates a response (LLM), and streams back TTS audio. Barge-in is supported: if the user speaks while the assistant is talking, the response is cancelled immediately.

## Prerequisites

- Ubuntu with NVIDIA GPU (tested on 4070 Ti SUPER, 16 GB VRAM)
- Python 3.13+
- CUDA 12.x drivers installed
- llama.cpp built with CUDA (see below)
- A GGUF model for the LLM

## Setup

### 1. Python environment

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate

# Install PyTorch with CUDA (must be done separately)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# Install the rest
pip install -r requirements.txt
```

### 2. Build llama.cpp

```bash
git clone https://github.com/ggml-org/llama.cpp ~/llama.cpp
cmake ~/llama.cpp -B ~/llama.cpp/build \
    -DBUILD_SHARED_LIBS=OFF \
    -DGGML_CUDA=ON \
    -DLLAMA_CURL=ON
cmake --build ~/llama.cpp/build --config Release -j$(nproc) --target llama-server
```

### 3. Download a model

Pick a model that fits your VRAM. With faster-whisper using ~1.5 GB, you have ~12 GB left for the LLM.

```bash
# Example: download directly from HuggingFace via llama-server
# (it downloads on first run when using -hf)
~/llama.cpp/build/bin/llama-server \
    -hf Qwen/Qwen3-8B-GGUF:Q4_K_M \
    --port 8080 -ngl 99 -c 4096 --host 127.0.0.1
```

Or download a GGUF file manually and point to it with `-m /path/to/model.gguf`.

## Running

### Start the LLM server (terminal 1)

```bash
~/llama.cpp/build/bin/llama-server \
    -hf Qwen/Qwen3-8B-GGUF:Q4_K_M \
    --port 8080 -ngl 99 -c 4096 --host 127.0.0.1
```

### Start the voice agent (terminal 2)

```bash
cd server
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8765
```

On first run, the Whisper and Piper models are downloaded automatically from HuggingFace. This may take a few minutes.

Once you see `All models loaded. Server ready.` in the logs, the server is accepting WebSocket connections at `ws://<your-ip>:8765/ws`.

## Configuration

Edit `server/config.yaml` to change settings:

```yaml
stt:
  model: "distil-large-v3"    # or "large-v3" for better accuracy
  language: "fr"               # change language here

llm:
  base_url: "http://127.0.0.1:8080"
  max_tokens: 512
  temperature: 0.7

tts:
  model: "fr_FR-siwis-medium"  # Piper voice model name

vad:
  threshold: 0.5               # speech detection sensitivity
  min_silence_ms: 700          # silence duration to end a turn
  min_speech_ms: 250           # minimum speech to avoid false triggers
```

All settings can be overridden with environment variables using the `KIDSAI_` prefix (e.g. `KIDSAI_whisper_language=en`).

## WebSocket Protocol

The client connects to `ws://<host>:8765/ws` and communicates using:

**Client to server:**
- Binary frames: 16 kHz mono s16le PCM audio, 512 samples (1024 bytes) per frame
- Text frames (JSON): `{"type": "interrupt"}` to cancel the current response

**Server to client:**
- Binary frames: TTS audio as s16le PCM (at the sample rate specified in `tts_config`)
- Text frames (JSON):

| Message | Description |
|---------|-------------|
| `{"type": "tts_config", "sample_rate": 22050, "channels": 1, "format": "s16le"}` | Sent once on connect. Tells the client what format the TTS audio will be in. |
| `{"type": "state", "state": "LISTENING\|THINKING\|SPEAKING\|IDLE"}` | State machine transitions. |
| `{"type": "transcript", "text": "...", "role": "user"}` | What the user said (STT result). |
| `{"type": "transcript", "text": "...", "role": "assistant"}` | What the assistant said (full LLM response). |
| `{"type": "error", "message": "..."}` | Error info. |

## VRAM Usage

| Component | VRAM |
|-----------|------|
| faster-whisper distil-large-v3 | ~1.5 GB |
| llama.cpp 7B Q4_K_M | ~5 GB |
| llama.cpp 3B Q4_K_M | ~2.5 GB |
| Silero VAD | CPU only |
| Piper TTS | CPU only |

## Mobile App

The client is a React Native app that shows a full-screen animated robot face. It streams mic audio to the server and plays back TTS responses. No buttons — the server's VAD detects speech automatically.

### Prerequisites

- Node.js 20+
- Android SDK (via Android Studio)
- A physical Android device or emulator

### Setup

```bash
cd mobile-app
npm install
```

Edit `src/config.ts` to set `WS_URL` to your server's IP address (e.g. `ws://192.168.1.100:8765/ws`).

### Running

```bash
cd mobile-app
npx react-native run-android
```

### Tests

```bash
cd mobile-app
npx jest
```

## Server Tests

```bash
cd server
source .venv/bin/activate
pytest tests/ -v
```

## Project Structure

```
kids-ai/
├── server/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, model loading, WebSocket endpoint
│   │   ├── config.py               # Settings from config.yaml + env vars
│   │   ├── session.py              # Session state machine, async pipeline orchestrator
│   │   ├── pipeline/
│   │   │   ├── vad.py              # Silero VAD speech detection + buffering
│   │   │   ├── stt.py              # faster-whisper transcription
│   │   │   ├── llm.py              # Async streaming client for llama.cpp
│   │   │   ├── tts.py              # Piper TTS synthesis
│   │   │   └── sentence_chunker.py # Split LLM output at sentence boundaries for early TTS
│   │   └── audio/
│   │       └── codec.py            # PCM / float32 conversions
│   ├── tests/
│   ├── config.yaml
│   └── requirements.txt
└── mobile-app/                     # React Native Android client
    ├── App.tsx                     # Root component
    ├── src/
    │   ├── config.ts               # Server URL, audio constants
    │   ├── hooks/
    │   │   ├── useWebSocket.ts     # Binary WebSocket with auto-reconnect
    │   │   ├── useSessionState.ts  # State machine (IDLE/LISTENING/THINKING/SPEAKING)
    │   │   ├── useAudioCapture.ts  # Mic → s16le PCM → WebSocket
    │   │   └── useAudioPlayback.ts # WebSocket → s16le PCM → speaker
    │   ├── components/
    │   │   ├── VoiceSession.tsx    # Invisible orchestrator wiring hooks + context
    │   │   ├── RobotFace.tsx       # Full-screen animated face
    │   │   ├── Eyes.tsx            # Animated eyes (blink, wide, look-around, squint)
    │   │   └── Mouth.tsx           # Animated mouth (smile, circle, wavy, talking)
    │   └── utils/
    │       └── pcm.ts              # Float32 ↔ s16le conversions
    └── __tests__/                  # Jest unit + integration tests
```
