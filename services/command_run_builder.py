from __future__ import annotations

from datetime import datetime

from schemas.command import CommandNormalizationResult
from schemas.command_run import CommandArtifacts, CommandMetadata


class CommandRunBuilder:
    def build_metadata(
        self,
        *,
        artifacts: CommandArtifacts,
        run_id: str,
        timestamp: datetime,
        duration_seconds: float,
        sample_rate: int,
        source_text: str,
        source_modality: str,
        normalization_result: CommandNormalizationResult,
        inference_seconds: float,
        asr_family: str,
        asr_provider: str,
        asr_model_name: str,
        existing_metadata: CommandMetadata | None = None,
    ) -> CommandMetadata:
        payload = {
            "id": run_id,
            "timestamp": timestamp,
            "duration_seconds": duration_seconds,
            "sample_rate": sample_rate,
            "audio_path": artifacts.audio_path,
            "source_text": source_text,
            "source_modality": source_modality,
            "language": normalization_result.source.language,
            "language_source": normalization_result.source.language_source,
            "command_en": normalization_result.normalized.text,
            "normalization_spans_path": artifacts.normalization_spans_path,
            "normalization_span_count": len(normalization_result.spans),
            "target_language": normalization_result.normalized.target_language,
            "normalization_status": normalization_result.normalized.status,
            "normalization_message": normalization_result.normalized.message,
            "translation_status": normalization_result.normalized.status,
            "translation_message": normalization_result.normalized.message,
            "inference_seconds": inference_seconds,
            "asr_family": asr_family,
            "asr_provider": asr_provider,
            "asr_model_name": asr_model_name,
            "translation_family": normalization_result.normalized.translation_family,
            "translation_provider": normalization_result.normalized.translation_provider,
            "translation_model_name": normalization_result.normalized.translation_model_name,
            "translation_inference_seconds": (
                normalization_result.normalized.translation_inference_seconds
            ),
            "pcs_status": normalization_result.normalized.pcs_status,
            "pcs_message": normalization_result.normalized.pcs_message,
            "pcs_family": normalization_result.normalized.pcs_family,
            "pcs_provider": normalization_result.normalized.pcs_provider,
            "pcs_model_name": normalization_result.normalized.pcs_model_name,
            "pcs_inference_seconds": normalization_result.normalized.pcs_inference_seconds,
        }
        if existing_metadata is not None:
            return existing_metadata.model_copy(update=payload)
        return CommandMetadata(**payload)
