from __future__ import annotations

import logging
from collections.abc import Callable

from rich.console import Console

from schemas.config import (
    AppSettings,
    ASRSettings,
    PCSSettings,
    TranslationRouteSettings,
    TranslationSettings,
)
from schemas.model import ModelDescriptor, ModelRequest
from schemas.runtime import ModelPreparationResult, PipelinePreparationResult
from services.asr_assets import FasterWhisperAssetPreparer
from services.pcs_assets import TransformersPCSAssetPreparer
from services.translation_assets import TransformersTranslationAssetPreparer

logger = logging.getLogger(__name__)

SUPPORTED_TASKS = ("asr", "translation", "pcs")
SUPPORTED_ASR_FAMILIES = ("whisper",)
SUPPORTED_TRANSLATION_FAMILIES = ("m2m100", "opus_mt")
SUPPORTED_PCS_FAMILIES = ("punctuation",)


def infer_opus_mt_source_language(model_name: str) -> str | None:
    marker = "opus-mt-"
    normalized_model_name = model_name.lower()
    if marker not in normalized_model_name:
        return None

    language_pair = normalized_model_name.split(marker, maxsplit=1)[1].split("/", maxsplit=1)[0]
    parts = language_pair.split("-")
    if len(parts) < 2:
        return None
    return parts[-2]


def build_skipped_preparation_result(
    *,
    task: str,
    family: str,
    provider: str,
    model_name: str,
    model_source: str,
    download_root: str | None,
    local_files_only: bool,
    message: str,
) -> ModelPreparationResult:
    return ModelPreparationResult(
        task=task,
        family=family,
        provider=provider,
        model_name=model_name,
        model_source=model_source,
        download_root=download_root,
        local_files_only=local_files_only,
        ready=False,
        mode="skipped",
        message=message,
    )


def build_asr_model_descriptor(
    settings: AppSettings,
    *,
    family: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    local_files_only: bool | None = None,
) -> ModelDescriptor:
    resolved_settings = resolve_asr_settings(
        settings,
        family=family,
        provider=provider,
        model_name=model_name,
        local_files_only=local_files_only,
    )
    return ModelDescriptor(
        task="asr",
        family=resolved_settings.family,
        provider=resolved_settings.provider,
        model_name=resolved_settings.model_name,
        model_path=resolved_settings.model_path,
        download_root=resolved_settings.download_root,
        local_files_only=resolved_settings.local_files_only,
        device=resolved_settings.device,
        compute_type=resolved_settings.compute_type,
        beam_size=resolved_settings.beam_size,
        cpu_threads=resolved_settings.cpu_threads,
        num_workers=resolved_settings.num_workers,
    )


def build_translation_model_descriptor(
    settings: AppSettings,
    *,
    family: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    source_language: str | None = None,
    target_language: str | None = None,
    local_files_only: bool | None = None,
) -> ModelDescriptor:
    resolved_settings = resolve_translation_settings(
        settings,
        family=family,
        provider=provider,
        model_name=model_name,
        source_language=source_language,
        target_language=target_language,
        local_files_only=local_files_only,
    )
    return ModelDescriptor(
        task="translation",
        family=resolved_settings.family,
        provider=resolved_settings.provider,
        model_name=resolved_settings.model_name,
        model_path=resolved_settings.model_path,
        download_root=resolved_settings.download_root,
        local_files_only=resolved_settings.local_files_only,
        source_language=resolved_settings.source_language,
        target_language=resolved_settings.target_language,
        device=resolved_settings.device,
        cpu_threads=resolved_settings.cpu_threads,
        max_length=resolved_settings.max_length,
    )


def build_translation_route_descriptors(settings: AppSettings) -> list[ModelDescriptor]:
    descriptors = [
        build_translation_model_descriptor(
            settings,
            family=settings.translation.family,
            provider=settings.translation.provider,
            model_name=settings.translation.model_name,
            source_language=settings.translation.source_language,
            target_language=settings.translation.target_language,
            local_files_only=settings.translation.local_files_only,
        )
    ]
    descriptors.extend(
        _build_translation_descriptor_from_route(route)
        for route in sorted(settings.translation_routes, key=lambda route: route.priority)
        if route.enabled
    )

    unique_descriptors: list[ModelDescriptor] = []
    seen_keys: set[tuple[str, str, str, str | None, str | None, str | None]] = set()
    for descriptor in descriptors:
        key = (
            descriptor.family,
            descriptor.provider,
            descriptor.model_name,
            descriptor.source_language,
            descriptor.target_language,
            str(descriptor.download_root) if descriptor.download_root is not None else None,
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_descriptors.append(descriptor)
    return unique_descriptors


def build_translation_route_requests(
    settings: AppSettings,
    *,
    local_files_only: bool | None = None,
    force_download: bool = False,
) -> list[ModelRequest]:
    requests = []
    for descriptor in build_translation_route_descriptors(settings):
        effective_descriptor = descriptor
        if local_files_only is not None:
            effective_descriptor = descriptor.model_copy(
                update={"local_files_only": local_files_only}
            )
        requests.append(
            ModelRequest(
                descriptor=effective_descriptor,
                force_download=force_download,
            )
        )
    return requests


def build_pcs_model_descriptor(
    settings: AppSettings,
    *,
    family: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    local_files_only: bool | None = None,
) -> ModelDescriptor:
    resolved_settings = resolve_pcs_settings(
        settings,
        family=family,
        provider=provider,
        model_name=model_name,
        local_files_only=local_files_only,
    )
    return ModelDescriptor(
        task="pcs",
        family=resolved_settings.family,
        provider=resolved_settings.provider,
        model_name=resolved_settings.model_name,
        model_path=resolved_settings.model_path,
        download_root=resolved_settings.download_root,
        local_files_only=resolved_settings.local_files_only,
        device=resolved_settings.device,
        cpu_threads=resolved_settings.cpu_threads,
        max_length=resolved_settings.max_length,
    )


def build_asr_model_request(
    settings: AppSettings,
    *,
    family: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    local_files_only: bool | None = None,
    force_download: bool = False,
) -> ModelRequest:
    return ModelRequest(
        descriptor=build_asr_model_descriptor(
            settings,
            family=family,
            provider=provider,
            model_name=model_name,
            local_files_only=local_files_only,
        ),
        force_download=force_download,
    )


def build_translation_model_request(
    settings: AppSettings,
    *,
    family: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    source_language: str | None = None,
    target_language: str | None = None,
    local_files_only: bool | None = None,
    force_download: bool = False,
) -> ModelRequest:
    return ModelRequest(
        descriptor=build_translation_model_descriptor(
            settings,
            family=family,
            provider=provider,
            model_name=model_name,
            source_language=source_language,
            target_language=target_language,
            local_files_only=local_files_only,
        ),
        force_download=force_download,
    )


def build_pcs_model_request(
    settings: AppSettings,
    *,
    family: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    local_files_only: bool | None = None,
    force_download: bool = False,
) -> ModelRequest:
    return ModelRequest(
        descriptor=build_pcs_model_descriptor(
            settings,
            family=family,
            provider=provider,
            model_name=model_name,
            local_files_only=local_files_only,
        ),
        force_download=force_download,
    )


def resolve_asr_settings(
    settings: AppSettings,
    *,
    family: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    local_files_only: bool | None = None,
) -> ASRSettings:
    resolved_family = (family or settings.asr.family).lower()
    resolved_provider = (provider or settings.asr.provider).lower()
    if resolved_family not in SUPPORTED_ASR_FAMILIES:
        raise ValueError(f"Unsupported ASR family: {resolved_family}")
    if resolved_family == "whisper" and resolved_provider != "faster_whisper":
        raise ValueError(
            "Unsupported ASR provider for whisper family: "
            f"{resolved_provider}. Expected `faster_whisper`."
        )

    update: dict[str, object] = {
        "family": resolved_family,
        "provider": resolved_provider,
    }
    if model_name is not None:
        update["model_name"] = model_name
    if local_files_only is not None:
        update["local_files_only"] = local_files_only
    return settings.asr.model_copy(update=update)


def resolve_translation_settings(
    settings: AppSettings,
    *,
    family: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    source_language: str | None = None,
    target_language: str | None = None,
    local_files_only: bool | None = None,
) -> TranslationSettings:
    resolved_family = (family or settings.translation.family).lower()
    resolved_provider = (provider or settings.translation.provider).lower()
    if resolved_family not in SUPPORTED_TRANSLATION_FAMILIES:
        raise ValueError(f"Unsupported translation family: {resolved_family}")
    if resolved_provider != "transformers":
        raise ValueError(
            f"Unsupported translation provider: {resolved_provider}. Expected `transformers`."
        )

    update: dict[str, object] = {
        "family": resolved_family,
        "provider": resolved_provider,
    }
    if model_name is not None:
        update["model_name"] = model_name
    if source_language is not None:
        update["source_language"] = source_language
    if target_language is not None:
        update["target_language"] = target_language
    if local_files_only is not None:
        update["local_files_only"] = local_files_only
    resolved_settings = settings.translation.model_copy(update=update)
    if resolved_family == "opus_mt" and resolved_settings.source_language is None:
        inferred_source_language = infer_opus_mt_source_language(resolved_settings.model_name)
        if inferred_source_language is not None:
            resolved_settings = resolved_settings.model_copy(
                update={"source_language": inferred_source_language}
            )
    return resolved_settings


def resolve_pcs_settings(
    settings: AppSettings,
    *,
    family: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    local_files_only: bool | None = None,
) -> PCSSettings:
    resolved_family = (family or settings.pcs.family).lower()
    resolved_provider = (provider or settings.pcs.provider).lower()
    if resolved_family not in SUPPORTED_PCS_FAMILIES:
        raise ValueError(f"Unsupported PCS family: {resolved_family}")
    if resolved_provider not in {"transformers", "onnx"}:
        raise ValueError(
            f"Unsupported PCS provider: {resolved_provider}. Expected `transformers` or `onnx`."
        )

    update: dict[str, object] = {
        "family": resolved_family,
        "provider": resolved_provider,
    }
    if model_name is not None:
        update["model_name"] = model_name
    if local_files_only is not None:
        update["local_files_only"] = local_files_only
    return settings.pcs.model_copy(update=update)


def _build_translation_descriptor_from_route(route: TranslationRouteSettings) -> ModelDescriptor:
    source_language = route.source_language
    if route.family == "opus_mt" and source_language is None:
        source_language = infer_opus_mt_source_language(route.model_name)
    return ModelDescriptor(
        task="translation",
        family=route.family,
        provider=route.provider,
        model_name=route.model_name,
        model_path=route.model_path,
        download_root=route.download_root,
        local_files_only=route.local_files_only,
        source_language=source_language,
        target_language=route.target_language,
        device=route.device,
        cpu_threads=route.cpu_threads,
        max_length=route.max_length,
    )


def prepare_model(
    request: ModelRequest,
    console: Console | None = None,
) -> ModelPreparationResult:
    descriptor = request.descriptor
    resolved_task = descriptor.task.lower()
    if resolved_task not in SUPPORTED_TASKS:
        raise ValueError(f"Unsupported task: {resolved_task}")

    if resolved_task == "asr":
        asr_settings = ASRSettings.model_validate(
            {
                "family": descriptor.family,
                "provider": descriptor.provider,
                "model_name": descriptor.model_name,
                "model_path": descriptor.model_path,
                "download_root": descriptor.download_root,
                "local_files_only": descriptor.local_files_only,
                "device": descriptor.device or "auto",
                "compute_type": descriptor.compute_type or "int8",
                "beam_size": descriptor.beam_size or 5,
                "cpu_threads": descriptor.cpu_threads or 0,
                "num_workers": descriptor.num_workers or 1,
            }
        )
        preparer = FasterWhisperAssetPreparer(asr_settings, console=console)
        return preparer.prepare(force_download=request.force_download)

    if resolved_task == "translation":
        translation_settings = TranslationSettings.model_validate(
            {
                "family": descriptor.family,
                "provider": descriptor.provider,
                "model_name": descriptor.model_name,
                "model_path": descriptor.model_path,
                "download_root": descriptor.download_root,
                "local_files_only": descriptor.local_files_only,
                "source_language": descriptor.source_language,
                "target_language": descriptor.target_language or "en",
                "device": descriptor.device or "auto",
                "cpu_threads": descriptor.cpu_threads or 0,
                "max_length": descriptor.max_length or 256,
            }
        )
        preparer = TransformersTranslationAssetPreparer(translation_settings, console=console)
        return preparer.prepare(force_download=request.force_download)

    pcs_settings = PCSSettings.model_validate(
        {
            "family": descriptor.family,
            "provider": descriptor.provider,
            "model_name": descriptor.model_name,
            "model_path": descriptor.model_path,
            "download_root": descriptor.download_root,
            "local_files_only": descriptor.local_files_only,
            "device": descriptor.device or "auto",
            "cpu_threads": descriptor.cpu_threads or 0,
            "max_length": descriptor.max_length or 256,
        }
    )
    preparer = TransformersPCSAssetPreparer(pcs_settings, console=console)
    return preparer.prepare(force_download=request.force_download)


def prepare_configured_models(
    settings: AppSettings,
    *,
    force_download: bool = False,
    console: Console | None = None,
    on_component_started: Callable[[ModelRequest, int, int], None] | None = None,
    on_component_prepared: Callable[[ModelPreparationResult], None] | None = None,
) -> PipelinePreparationResult:
    components: list[ModelPreparationResult] = []
    requests = [
        build_asr_model_request(
            settings,
            family=settings.asr.family,
            provider=settings.asr.provider,
            model_name=settings.asr.model_name,
            local_files_only=False,
            force_download=force_download,
        )
    ]

    if settings.translation.enabled:
        requests.extend(
            build_translation_route_requests(
                settings,
                local_files_only=False,
                force_download=force_download,
            )
        )
    if settings.pcs.enabled:
        requests.append(
            build_pcs_model_request(
                settings,
                family=settings.pcs.family,
                provider=settings.pcs.provider,
                model_name=settings.pcs.model_name,
                local_files_only=False,
                force_download=force_download,
            )
        )

    total_requests = len(requests)
    for index, request in enumerate(requests, start=1):
        if on_component_started is not None:
            on_component_started(request, index, total_requests)

        try:
            component = prepare_model(request, console=console)
        except RuntimeError as error:
            descriptor = request.descriptor
            if descriptor.task not in {"translation", "pcs"}:
                raise
            logger.warning("Skipping %s model preparation: %s", descriptor.task, error)
            component = build_skipped_preparation_result(
                task=descriptor.task,
                family=descriptor.family,
                provider=descriptor.provider,
                model_name=descriptor.model_name,
                model_source=descriptor.model_name,
                download_root=(
                    str(descriptor.download_root) if descriptor.download_root is not None else None
                ),
                local_files_only=False,
                message=str(error),
            )

        components.append(component)
        if on_component_prepared is not None:
            on_component_prepared(component)

    return PipelinePreparationResult(components=components)
