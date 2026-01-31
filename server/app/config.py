from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import model_validator
from pydantic_settings import BaseSettings


_SERVER_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8765

    # Audio format (what the client sends)
    sample_rate: int = 16000
    client_frame_ms: int = 32  # 32ms frames -> 512 samples @ 16kHz

    # VAD
    vad_threshold: float = 0.5
    vad_min_silence_ms: int = 700
    vad_min_speech_ms: int = 250

    # STT
    whisper_model: str = "distil-large-v3"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"
    whisper_beam_size: int = 5
    whisper_language: str = "fr"

    # LLM
    llm_base_url: str = "http://127.0.0.1:8080"
    llm_model: str = "local-model"
    llm_max_tokens: int = 512
    llm_temperature: float = 0.7

    # TTS
    piper_model: str = "fr_FR-siwis-medium"
    piper_speaker: int | None = None
    tts_sentence_silence: float = 0.3

    # System prompt
    system_prompt_file: str = "app/prompts/system.txt"

    @model_validator(mode="before")
    @classmethod
    def _load_yaml(cls, values: dict[str, Any]) -> dict[str, Any]:
        yaml_path = _SERVER_ROOT / "config.yaml"
        if not yaml_path.exists():
            return values

        with open(yaml_path) as f:
            yaml_data: dict[str, Any] = yaml.safe_load(f) or {}

        # Map YAML section names to field name prefixes
        section_prefix: dict[str, str] = {
            "server": "",           # host, port (no prefix)
            "audio": "",            # sample_rate (no prefix)
            "vad": "vad_",
            "stt": "whisper_",      # stt.model -> whisper_model
            "llm": "llm_",
            "tts": "tts_",          # except piper_model handled below
        }
        # Special mappings where YAML key != field name
        special: dict[tuple[str, str], str] = {
            ("tts", "model"): "piper_model",
            ("tts", "sentence_silence"): "tts_sentence_silence",
        }

        flat: dict[str, Any] = {}
        for section_name, entries in yaml_data.items():
            assert isinstance(section_name, str)
            if isinstance(entries, dict):
                prefix = section_prefix.get(section_name, f"{section_name}_")
                typed_entries: dict[str, Any] = dict(entries)  # type: ignore[arg-type]
                for key, val in typed_entries.items():
                    flat_key = special.get((section_name, key), f"{prefix}{key}")
                    flat[flat_key] = val
            else:
                flat[section_name] = entries

        # Explicit env / constructor values take precedence over YAML
        flat.update({k: v for k, v in values.items() if v is not None})
        return flat

    def get_system_prompt(self) -> str:
        path = _SERVER_ROOT / self.system_prompt_file
        if path.exists():
            return path.read_text().strip()
        return "Tu es un assistant vocal gentil et patient pour les enfants."

    class Config:
        env_prefix = "KIDSAI_"


settings = Settings()
