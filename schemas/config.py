from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.language import normalize_language_code


class ModelComponentSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    family: str
    provider: str
    model_name: str
    model_path: Path | None = None
    download_root: Path | None = None
    local_files_only: bool = True
    preload_on_startup: bool = False

    @field_validator("model_path", "download_root", mode="before")
    @classmethod
    def empty_path_to_none(cls, value: str | Path | None) -> Path | None:
        if value in ("", None):
            return None
        return Path(value)


class ASRSettings(ModelComponentSettings):
    family: str = "whisper"
    provider: str = "faster_whisper"
    model_name: str = "small"
    device: str = "auto"
    compute_type: str = "int8"
    language: str | None = None
    beam_size: int = Field(default=5, ge=1)
    cpu_threads: int = Field(default=0, ge=0)
    num_workers: int = Field(default=1, ge=1)
    download_root: Path | None = None

    @field_validator("language", mode="before")
    @classmethod
    def empty_language_to_none(cls, value: str | None) -> str | None:
        return normalize_language_code(value)


class TranslationSettings(ModelComponentSettings):
    enabled: bool = True
    family: str = "m2m100"
    provider: str = "transformers"
    model_name: str = "facebook/m2m100_418M"
    source_language: str | None = None
    target_language: str = "en"
    device: str = "auto"
    cpu_threads: int = Field(default=0, ge=0)
    max_length: int = Field(default=256, ge=16)
    download_root: Path | None = None

    @field_validator("source_language", mode="before")
    @classmethod
    def empty_source_language_to_none(cls, value: str | None) -> str | None:
        return normalize_language_code(value)

    @field_validator("target_language", mode="before")
    @classmethod
    def normalize_target_language(cls, value: str | None) -> str:
        return normalize_language_code(value) or "en"


class StorageSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    runs_dir: Path = Path("runs")
    data_dir: Path = Path("data")
    samples_dir: Path = Path("samples")


class LoggingSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    level: str = "INFO"
    rich: bool = True


class APISettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    app_name: str = "iVoice"
    asr: ASRSettings = ASRSettings()
    translation: TranslationSettings = TranslationSettings()
    storage: StorageSettings = StorageSettings()
    logging: LoggingSettings = LoggingSettings()
    api: APISettings = APISettings()
