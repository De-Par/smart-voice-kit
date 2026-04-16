from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from schemas.runtime import ASRPreparationResult
from schemas.transcription import TranscriptionRun
from services.bootstrap import AppContext


def format_bytes(value: int) -> str:
    size = float(value)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{value} B"


def format_dbfs(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f} dBFS"


def build_details_text(
    context: AppContext,
    input_devices: Sequence[Any],
    current_device_index: int,
    current_audio_stats: Mapping[str, str],
    last_prepare_result: ASRPreparationResult | None,
    last_run: TranscriptionRun | None,
) -> str:
    sections: list[str] = []

    asr = context.settings.asr
    sections.append(
        "\n".join(
            [
                "[Model]",
                f"backend: {context.service.asr_engine.backend_name}",
                f"model: {context.service.asr_engine.model_name}",
                f"device: {asr.device}",
                f"compute_type: {asr.compute_type}",
                f"offline_only: {asr.local_files_only}",
                f"download_root: {asr.download_root}",
            ]
        )
    )

    device_text = "<none>"
    if 0 <= current_device_index < len(input_devices):
        device_text = input_devices[current_device_index].description()
    sections.append("[Audio Input]\n" + f"device: {device_text}")

    if current_audio_stats:
        sections.append(
            "[Current Audio]\n"
            + "\n".join(f"{key}: {value}" for key, value in current_audio_stats.items())
        )

    if last_prepare_result is not None:
        downloaded_files = (
            f"{last_prepare_result.downloaded_files}/{last_prepare_result.total_files}"
        )
        sections.append(
            "[Last Prepare]\n"
            + "\n".join(
                [
                    f"mode: {last_prepare_result.mode}",
                    f"downloaded_files: {downloaded_files}",
                    f"downloaded_bytes: {format_bytes(last_prepare_result.downloaded_bytes)}",
                    f"total_bytes: {format_bytes(last_prepare_result.total_bytes)}",
                ]
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
                    f"audio_path: {metadata.audio_path}",
                ]
            )
        )

    return "\n\n".join(sections)
