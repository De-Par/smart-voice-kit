from __future__ import annotations

from abc import ABC, abstractmethod

from schemas.runtime import ModelPreparationResult
from schemas.transcription import TranslationResult


class BaseTranslationEngine(ABC):
    family_name: str
    provider_name: str
    model_name: str

    def prepare(self) -> ModelPreparationResult:
        """Ensure translation assets are available locally for offline runtime."""
        raise NotImplementedError

    def normalize_language_code(self, value: str | None) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def translate(
        self,
        text: str,
        *,
        source_language: str | None = None,
        target_language: str = "en",
    ) -> TranslationResult:
        """Translate a transcript into the target language."""
