from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from core.asr import build_asr_engine
from core.logging import configure_logging
from core.pcs import build_pcs_engine
from core.settings import load_settings
from schemas.config import AppSettings
from services.command_normalization import CommandNormalizationService
from services.command_service import CommandService
from services.prepare_model import (
    build_asr_model_descriptor,
    build_asr_model_request,
    build_pcs_model_descriptor,
    build_translation_model_descriptor,
    build_translation_route_descriptors,
)
from services.run_service import RunService
from services.run_store import RunArtifactStore
from services.translation_router import TranslationRouter


@dataclass(frozen=True)
class AppContext:
    settings: AppSettings
    service: CommandService


@lru_cache(maxsize=4)
def build_app_context(
    config_path: str | Path | None = None,
    asr_local_files_only_override: bool | None = None,
    warm_up_on_startup: bool | None = None,
) -> AppContext:
    settings = load_settings(config_path)
    if asr_local_files_only_override is not None:
        updated_asr = settings.asr.model_copy(
            update={"local_files_only": asr_local_files_only_override}
        )
        settings = settings.model_copy(update={"asr": updated_asr})
    configure_logging(settings.logging)
    asr_descriptor = build_asr_model_descriptor(settings)
    translation_descriptor = build_translation_model_descriptor(settings)
    translation_route_descriptors = build_translation_route_descriptors(settings)[1:]
    pcs_descriptor = build_pcs_model_descriptor(settings)
    asr_engine = build_asr_engine(asr_descriptor)
    pcs_engine = build_pcs_engine(pcs_descriptor)
    translation_router = TranslationRouter(
        default_descriptor=translation_descriptor,
        route_descriptors=translation_route_descriptors,
    )
    command_normalization_service = CommandNormalizationService(
        settings=settings,
        translation_router=translation_router,
        pcs_engine=pcs_engine,
    )
    run_store = RunArtifactStore()
    run_service = RunService(settings=settings, run_store=run_store)
    service = CommandService(
        settings=settings,
        asr_engine=asr_engine,
        asr_request=build_asr_model_request(settings),
        command_normalization_service=command_normalization_service,
        run_store=run_store,
        run_service=run_service,
    )
    should_warm_up = warm_up_on_startup
    if should_warm_up is None:
        should_warm_up = any(
            (
                settings.asr.preload_on_startup,
                settings.translation.preload_on_startup,
                settings.pcs.preload_on_startup,
            )
        )
    if should_warm_up:
        service.warm_up_pipeline()
    return AppContext(settings=settings, service=service)
