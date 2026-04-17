from __future__ import annotations

from core.asr.base import BaseASREngine
from core.asr.faster_whisper_engine import FasterWhisperASREngine
from schemas.model import ModelDescriptor


def build_asr_engine(descriptor: ModelDescriptor) -> BaseASREngine:
    family = descriptor.family.lower()
    provider = descriptor.provider.lower()

    if family == "whisper" and provider == "faster_whisper":
        return FasterWhisperASREngine(
            model_name=descriptor.model_name,
            model_path=descriptor.model_path,
            device=descriptor.device or "auto",
            compute_type=descriptor.compute_type or "int8",
            beam_size=descriptor.beam_size or 5,
            cpu_threads=descriptor.cpu_threads or 0,
            num_workers=descriptor.num_workers or 1,
            download_root=descriptor.download_root,
            local_files_only=descriptor.local_files_only,
        )

    raise ValueError(
        f"Unsupported ASR runtime: family={descriptor.family} provider={descriptor.provider}"
    )
