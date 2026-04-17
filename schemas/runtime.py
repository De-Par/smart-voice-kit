from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelPreparationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task: str
    family: str
    provider: str
    model_name: str
    model_source: str
    download_root: str | None = None
    local_files_only: bool
    ready: bool = True
    downloaded_files: int = 0
    total_files: int = 0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    mode: str = "verified"
    message: str | None = None


class PipelinePreparationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    components: list[ModelPreparationResult] = Field(default_factory=list)


ASRPreparationResult = ModelPreparationResult
