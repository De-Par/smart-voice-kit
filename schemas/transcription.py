from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TranscriptionSegment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str


class TranscriptionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transcript: str
    language: str | None = None
    inference_seconds: float = Field(ge=0)
    asr_family: str
    asr_provider: str
    model_name: str
    segments: list[TranscriptionSegment] = Field(default_factory=list)


class TranslationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str
    source_language: str | None = None
    target_language: str = "en"
    inference_seconds: float = Field(ge=0)
    translation_family: str
    translation_provider: str
    model_name: str


class RunMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    timestamp: datetime
    duration_seconds: float = Field(ge=0)
    sample_rate: int = Field(ge=1)
    audio_path: str
    language: str | None = None
    transcript: str
    transcript_en: str
    target_language: str = "en"
    translation_status: str = "disabled"
    translation_message: str | None = None
    inference_seconds: float = Field(ge=0)
    asr_family: str
    asr_provider: str
    asr_model_name: str
    translation_family: str | None = None
    translation_provider: str | None = None
    translation_model_name: str | None = None
    translation_inference_seconds: float | None = Field(default=None, ge=0)


class TranscriptionRun(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_dir: str
    audio_path: str
    transcript_path: str
    transcript_en_path: str
    metadata_path: str
    metadata: RunMetadata
