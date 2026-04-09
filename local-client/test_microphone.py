#!/usr/bin/env python3
"""Test microphone input and VAD detection locally."""

import numpy as np
import sounddevice as sd
import torch
from silero_vad import load_silero_vad

# Audio settings
SAMPLE_RATE = 16_000
BLOCKSIZE = 512  # 32 ms @ 16 kHz
DTYPE = "int16"

# VAD settings
THRESHOLD = 0.5

# Load VAD model
print("Loading VAD model...")
vad_model = load_silero_vad(onnx=True)
vad_model.reset_states()
print("VAD model loaded\n")


def make_callback(threshold):
    def audio_callback(indata, frames, time, status):
        """Process each audio chunk and display VAD confidence."""
        if status:
            print(f"Status: {status}")

        # Convert to float32 for VAD
        audio_f32 = indata[:, 0].astype(np.float32) / 32768.0
        chunk_tensor = torch.from_numpy(audio_f32)

        # Get VAD confidence
        confidence = vad_model(chunk_tensor, SAMPLE_RATE).item()

        # Calculate audio level
        rms = np.sqrt(np.mean(audio_f32 ** 2))
        db = 20 * np.log10(max(rms, 1e-10))

        # Display with visual bar
        is_speech = confidence >= threshold
        bar_length = int(confidence * 50)
        bar = "=" * bar_length + " " * (50 - bar_length)

        status_str = "SPEECH" if is_speech else "silence"
        print(f"VAD: [{bar}] {confidence:.3f} | Level: {db:+.1f}dB | {status_str}", end="\r")
    return audio_callback


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test microphone and VAD")
    parser.add_argument("--device", type=int, help="Input device index to use")
    parser.add_argument("--threshold", type=float, default=THRESHOLD, help="VAD threshold (default: 0.5)")
    args = parser.parse_args()

    # List available devices
    print("Available audio devices:")
    devices = sd.query_devices()
    print(devices)
    print()

    # Select device
    if args.device is not None:
        device = args.device
        print(f"Using specified device: {device}")
    else:
        # Find pulse device (preferred)
        device = None
        for i, dev in enumerate(devices):
            if isinstance(dev, dict) and dev.get("name", "").startswith("pulse"):
                device = i
                break
        if device is not None:
            print(f"Using PulseAudio device: {device}")
        else:
            print("Using default device")

    threshold = args.threshold
    print(f"\nListening... (threshold: {threshold})")
    print("Speak into your microphone. Press Ctrl+C to stop.\n")

    # Start audio stream
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=DTYPE,
        blocksize=BLOCKSIZE,
        device=device,
        callback=make_callback(threshold),
    ):
        try:
            import time
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\nStopped.")


if __name__ == "__main__":
    main()
