from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from schemas.runtime import ModelPreparationResult
from schemas.transcription import TranscriptionResult


class BaseASREngine(ABC):
    family_name: str
    provider_name: str
    model_name: str

    def prepare(self) -> ModelPreparationResult:
        """Ensure speech-analysis model assets are available locally for later transcription."""
        raise NotImplementedError

    @abstractmethod
    def transcribe(self, audio_path: Path, language: str | None = None) -> TranscriptionResult:
        """Transcribe a local audio file into structured text"""
