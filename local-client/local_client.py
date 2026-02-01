#!/usr/bin/env python3
"""Local test client for the Kids-AI voice assistant server.

Captures microphone audio, streams it to the server over WebSocket,
and plays back TTS audio responses.

Usage:
    python local_client.py                          # connect to localhost:8765
    python local_client.py --url ws://host:port/ws  # custom server
    python local_client.py --list-devices           # show audio devices
"""

import argparse
import asyncio
import json
import sys
import threading

import numpy as np
import sounddevice as sd  # type: ignore[import-untyped]
from websockets.asyncio.client import ClientConnection, connect

# ---------------------------------------------------------------------------
# Defaults (matching server config)
# ---------------------------------------------------------------------------
SERVER_URL = "ws://localhost:8765/ws"
MIC_SAMPLE_RATE = 16_000
MIC_CHANNELS = 1
MIC_BLOCKSIZE = 512  # 512 samples = 1024 bytes = 32 ms @ 16 kHz
MIC_DTYPE = "int16"

PLAYBACK_BLOCKSIZE = 1024  # ~46 ms @ 22050 Hz


def _find_pulse_device() -> int | None:
    """Return the index of the 'pulse' ALSA device if available.

    Raw ALSA hw: devices often reject non-native sample rates (e.g. 16 kHz).
    PulseAudio/PipeWire transparently resamples, so we prefer it.
    """
    for i, dev in enumerate(sd.query_devices()):  # type: ignore[no-untyped-call]
        if isinstance(dev, dict) and dev.get("name", "").startswith("pulse"):
            return i
    return None


# ---------------------------------------------------------------------------
# Terminal colours (ANSI)
# ---------------------------------------------------------------------------
class C:
    RESET = "\033[0m"
    GREEN = "\033[32m"
    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    DIM = "\033[2m"


def _print_state(state: str) -> None:
    print(f"{C.GREEN}[{state}]{C.RESET}")


def _print_transcript(role: str, text: str) -> None:
    colour = C.CYAN if role == "user" else C.YELLOW
    label = "You" if role == "user" else "Assistant"
    print(f"{colour}{label}: {text}{C.RESET}")


def _print_error(msg: str) -> None:
    print(f"{C.RED}ERROR: {msg}{C.RESET}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Thread-safe playback buffer
# ---------------------------------------------------------------------------
class PlaybackRing:
    """Lock-protected byte buffer shared between asyncio and the audio thread."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self._lock = threading.Lock()

    def write(self, data: bytes) -> None:
        with self._lock:
            self._buf.extend(data)

    def read(self, n: int) -> bytes:
        with self._lock:
            available = min(n, len(self._buf))
            data = bytes(self._buf[:available])
            del self._buf[:available]
        if len(data) < n:
            data += b"\x00" * (n - len(data))
        return data

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()


# ---------------------------------------------------------------------------
# Sounddevice callbacks
# ---------------------------------------------------------------------------
def _make_mic_callback(
    loop: asyncio.AbstractEventLoop,
    mic_queue: asyncio.Queue[bytes],
):
    def callback(indata: np.ndarray, _frames: int, _time: object, status: sd.CallbackFlags) -> None:
        if status:
            print(f"{C.DIM}mic: {status}{C.RESET}", file=sys.stderr)
        try:
            loop.call_soon_threadsafe(mic_queue.put_nowait, indata.tobytes())
        except asyncio.QueueFull:
            pass  # drop frame rather than block the audio thread

    return callback


def _make_playback_callback(ring: PlaybackRing):
    def callback(outdata: np.ndarray, frames: int, _time: object, status: sd.CallbackFlags) -> None:
        if status:
            print(f"{C.DIM}speaker: {status}{C.RESET}", file=sys.stderr)
        raw = ring.read(frames * 2)  # 2 bytes per s16le sample
        outdata[:, 0] = np.frombuffer(raw, dtype=np.int16)

    return callback


# ---------------------------------------------------------------------------
# Async tasks
# ---------------------------------------------------------------------------
async def _send_audio(ws: ClientConnection, mic_queue: asyncio.Queue[bytes]) -> None:
    while True:
        pcm = await mic_queue.get()
        await ws.send(pcm)


async def _receive_messages(ws: ClientConnection, ring: PlaybackRing) -> None:
    prev_state = "IDLE"
    async for message in ws:
        if isinstance(message, bytes):
            ring.write(message)
            continue

        data = json.loads(message)
        msg_type = data.get("type")
        if msg_type == "state":
            state = data["state"]
            # Clear buffered audio only on barge-in (was SPEAKING, now interrupted)
            if prev_state == "SPEAKING" and state == "LISTENING":
                ring.clear()
            prev_state = state
            _print_state(state)
        elif msg_type == "transcript":
            _print_transcript(data["role"], data["text"])
        elif msg_type == "error":
            _print_error(data["message"])
        elif msg_type == "tts_config":
            pass  # handled before entering the main loop


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def _run(
    server_url: str,
    mic_device: int | None,
    speaker_device: int | None,
) -> None:
    loop = asyncio.get_running_loop()
    mic_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=50)
    ring = PlaybackRing()

    # Prefer PulseAudio/PipeWire over raw ALSA hw: devices (resampling support)
    pulse = _find_pulse_device()
    if mic_device is None and pulse is not None:
        mic_device = pulse
    if speaker_device is None and pulse is not None:
        speaker_device = pulse

    print(f"{C.DIM}Connecting to {server_url} ...{C.RESET}")
    async with connect(server_url) as ws:
        # First message should be tts_config
        first = await ws.recv()
        config = json.loads(first)
        playback_rate = 22_050
        if config.get("type") == "tts_config":
            playback_rate = config.get("sample_rate", playback_rate)
            print(f"{C.DIM}TTS: {playback_rate} Hz, s16le, mono{C.RESET}")

        mic_stream = sd.InputStream(
            samplerate=MIC_SAMPLE_RATE,
            channels=MIC_CHANNELS,
            dtype=MIC_DTYPE,
            blocksize=MIC_BLOCKSIZE,
            device=mic_device,
            callback=_make_mic_callback(loop, mic_queue),
        )
        playback_stream = sd.OutputStream(
            samplerate=playback_rate,
            channels=1,
            dtype="int16",
            blocksize=PLAYBACK_BLOCKSIZE,
            device=speaker_device,
            callback=_make_playback_callback(ring),
        )

        mic_stream.start()
        playback_stream.start()
        print(f"{C.DIM}Mic and speaker open. Speak to begin.{C.RESET}\n")

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(_send_audio(ws, mic_queue))
                tg.create_task(_receive_messages(ws, ring))
        finally:
            mic_stream.stop()
            mic_stream.close()
            playback_stream.stop()
            playback_stream.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Kids-AI local test client")
    parser.add_argument("--url", default=SERVER_URL, help="WebSocket server URL")
    parser.add_argument("--mic-device", type=int, default=None, help="Input device index")
    parser.add_argument("--speaker-device", type=int, default=None, help="Output device index")
    parser.add_argument("--list-devices", action="store_true", help="List audio devices and exit")
    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return

    try:
        asyncio.run(_run(args.url, args.mic_device, args.speaker_device))
    except KeyboardInterrupt:
        print(f"\n{C.DIM}Disconnected.{C.RESET}")


if __name__ == "__main__":
    main()
