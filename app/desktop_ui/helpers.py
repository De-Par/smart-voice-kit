from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from core.formatting import format_bytes
from schemas.runtime import PipelinePreparationResult
from schemas.transcription import TranscriptionRun
from services.bootstrap import AppContext


def build_details_text(
    context: AppContext,
    input_devices: Sequence[Any],
    current_device_index: int,
    current_audio_stats: Mapping[str, str],
    last_prepare_result: PipelinePreparationResult | None,
    last_run: TranscriptionRun | None,
) -> str:
    sections: list[str] = []

    asr = context.settings.asr
    sections.append(
        "\n".join(
            [
                "[Model]",
                f"family: {context.service.asr_engine.family_name}",
                f"provider: {context.service.asr_engine.provider_name}",
                f"model: {context.service.asr_engine.model_name}",
                f"device: {asr.device}",
                f"compute_type: {asr.compute_type}",
                f"offline_only: {asr.local_files_only}",
                f"download_root: {asr.download_root}",
            ]
        )
    )
    translation = context.settings.translation
    sections.append(
        "\n".join(
            [
                "[Translation]",
                f"enabled: {translation.enabled}",
                f"family: {context.service.translation_engine.family_name}",
                f"provider: {context.service.translation_engine.provider_name}",
                f"model: {context.service.translation_engine.model_name}",
                f"target_language: {translation.target_language}",
                f"download_root: {translation.download_root}",
            ]
        )
    )

    device_text = "<none>"
    if not input_devices:
        device_text = "<not initialized>"
    elif 0 <= current_device_index < len(input_devices):
        device_text = input_devices[current_device_index].description()
    sections.append("[Audio Input]\n" + f"device: {device_text}")

    if current_audio_stats:
        sections.append(
            "[Current Audio]\n"
            + "\n".join(f"{key}: {value}" for key, value in current_audio_stats.items())
        )

    if last_prepare_result is not None:
        for component in last_prepare_result.components:
            downloaded_files = f"{component.downloaded_files}/{component.total_files}"
            sections.append(
                f"[Last Prepare: {component.task}]\n"
                + "\n".join(
                    [
                        f"mode: {component.mode}",
                        f"family: {component.family}",
                        f"provider: {component.provider}",
                        f"model: {component.model_name}",
                        f"downloaded_files: {downloaded_files}",
                        f"downloaded_bytes: {format_bytes(component.downloaded_bytes)}",
                        f"total_bytes: {format_bytes(component.total_bytes)}",
                    ]
                    + ([f"message: {component.message}"] if component.message else [])
                )
            )

    if last_run is not None:
        metadata = last_run.metadata
        sections.append(
            "[Last Run]\n"
            + "\n".join(
                [
                    f"run_id: {metadata.id}",
                    f"language: {metadata.language or '<unknown>'}",
                    f"inference: {metadata.inference_seconds:.2f}s",
                    f"translation_status: {metadata.translation_status}",
                    f"translation_family: {metadata.translation_family or '<disabled>'}",
                    f"translation_provider: {metadata.translation_provider or '<disabled>'}",
                    f"audio_path: {metadata.audio_path}",
                ]
                + (
                    [f"translation_message: {metadata.translation_message}"]
                    if metadata.translation_message
                    else []
                )
            )
        )

    return "\n\n".join(sections)
