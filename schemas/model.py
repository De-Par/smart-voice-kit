from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.language import normalize_language_code


class ModelDescriptor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task: str
    family: str
    provider: str
    model_name: str
    model_path: Path | None = None
    download_root: Path | None = None
    local_files_only: bool = True
    source_language: str | None = None
    target_language: str | None = None
    device: str | None = None
    compute_type: str | None = None
    beam_size: int | None = Field(default=None, ge=1)
    cpu_threads: int | None = Field(default=None, ge=0)
    num_workers: int | None = Field(default=None, ge=1)
    max_length: int | None = Field(default=None, ge=1)

    @field_validator("model_path", "download_root", mode="before")
    @classmethod
    def empty_path_to_none(cls, value: str | Path | None) -> Path | None:
        if value in ("", None):
            return None
        return Path(value)

    @field_validator("source_language", "target_language", mode="before")
    @classmethod
    def normalize_language_fields(cls, value: str | None) -> str | None:
        return normalize_language_code(value)


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    descriptor: ModelDescriptor
    force_download: bool = False
