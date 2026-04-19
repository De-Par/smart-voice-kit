from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import TypeVar

from schemas.config import (
    AppSettings,
    ASRSettings,
    StorageSettings,
    TranslationRouteSettings,
    TranslationSettings,
)

DEFAULT_CONFIG_PATH = Path("config.toml")
ComponentSettingsT = TypeVar(
    "ComponentSettingsT",
    ASRSettings,
    TranslationSettings,
    TranslationRouteSettings,
)


def _resolve_storage(base_dir: Path, storage: StorageSettings) -> StorageSettings:
    return storage.model_copy(
        update={
            "runs_dir": (base_dir / storage.runs_dir).resolve()
            if not storage.runs_dir.is_absolute()
            else storage.runs_dir,
            "data_dir": (base_dir / storage.data_dir).resolve()
            if not storage.data_dir.is_absolute()
            else storage.data_dir,
            "samples_dir": (base_dir / storage.samples_dir).resolve()
            if not storage.samples_dir.is_absolute()
            else storage.samples_dir,
        }
    )


def _resolve_component_paths(
    base_dir: Path,
    component: ComponentSettingsT,
) -> ComponentSettingsT:
    return component.model_copy(
        update={
            "model_path": (base_dir / component.model_path).resolve()
            if component.model_path is not None and not component.model_path.is_absolute()
            else component.model_path,
            "download_root": (base_dir / component.download_root).resolve()
            if component.download_root is not None and not component.download_root.is_absolute()
            else component.download_root,
        }
    )


def _default_model_root(storage: StorageSettings, task: str, family: str) -> Path:
    return storage.data_dir / "models" / task / family


def load_settings(config_path: str | Path | None = None) -> AppSettings:
    raw_path = Path(config_path or os.getenv("VOICE_APP_CONFIG", DEFAULT_CONFIG_PATH))
    config_file = raw_path.resolve()
    payload: dict = {}

    if config_file.exists():
        payload = tomllib.loads(config_file.read_text(encoding="utf-8"))
        base_dir = config_file.parent
    else:
        base_dir = Path.cwd()

    settings = AppSettings.model_validate(payload)
    resolved_storage = _resolve_storage(base_dir, settings.storage)
    resolved_asr_base = _resolve_component_paths(base_dir, settings.asr)
    resolved_translation_base = _resolve_component_paths(base_dir, settings.translation)
    resolved_route_bases = [
        _resolve_component_paths(base_dir, route) for route in settings.translation_routes
    ]
    resolved_asr = resolved_asr_base.model_copy(
        update={
            "download_root": resolved_asr_base.download_root
            or _default_model_root(resolved_storage, "asr", settings.asr.family)
        }
    )
    resolved_translation = resolved_translation_base.model_copy(
        update={
            "download_root": resolved_translation_base.download_root
            or _default_model_root(
                resolved_storage,
                "translation",
                settings.translation.family,
            )
        }
    )
    resolved_translation_routes = [
        route.model_copy(
            update={
                "download_root": route.download_root
                or _default_model_root(
                    resolved_storage,
                    "translation",
                    route.family,
                )
            }
        )
        for route in resolved_route_bases
    ]

    for directory in (
        resolved_storage.runs_dir,
        resolved_storage.data_dir,
        resolved_storage.samples_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    for component in (resolved_asr, resolved_translation, *resolved_translation_routes):
        if component.download_root is not None:
            component.download_root.mkdir(parents=True, exist_ok=True)

    return settings.model_copy(
        update={
            "storage": resolved_storage,
            "asr": resolved_asr,
            "translation": resolved_translation,
            "translation_routes": resolved_translation_routes,
        }
    )
