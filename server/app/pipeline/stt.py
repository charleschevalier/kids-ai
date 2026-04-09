from __future__ import annotations

from typing import Any

import numpy as np
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline  # type: ignore[import-untyped]


class STTProcessor:
    """Wraps a HuggingFace Whisper model. Transcribes complete VAD-segmented utterances."""

    def __init__(
        self,
        model: Any,
        processor: Any,
        language: str = "fr",
        beam_size: int = 5,
    ) -> None:
        self.model = model
        self.processor = processor
        self.language = language
        self.beam_size = beam_size

    def transcribe(self, pcm_s16le: bytes) -> str:
        """Transcribe raw 16kHz s16le PCM bytes to text.

        This is BLOCKING — run in an executor.
        """
        audio = np.frombuffer(pcm_s16le, dtype=np.int16).astype(np.float32) / 32768.0

        # Process audio directly with the feature extractor
        inputs = self.processor(
            audio,
            sampling_rate=16000,
            return_tensors="pt",
        )

        # Move inputs to same device and dtype as model
        inputs = {k: v.to(device=self.model.device, dtype=self.model.dtype) for k, v in inputs.items()}

        # Generate transcription
        with torch.no_grad():
            generated_ids = self.model.generate(
                **inputs,
                language=self.language,
                num_beams=self.beam_size,
            )

        # Decode the generated IDs to text
        text = self.processor.batch_decode(
            generated_ids,
            skip_special_tokens=True,
        )[0].strip()

        return text


def load_whisper_pipeline(
    model_id: str,
    device: str = "cuda",
    torch_dtype: str = "float16",
) -> tuple[Any, Any]:
    """Load a HuggingFace Whisper model and processor. Returns (model, processor)."""
    dtype = torch.float16 if torch_dtype == "float16" else torch.float32

    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
    ).to(device)

    processor = AutoProcessor.from_pretrained(model_id)

    return (model, processor)
