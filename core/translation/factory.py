from __future__ import annotations

from core.translation.base import BaseTranslationEngine
from core.translation.identity_engine import IdentityTranslationEngine
from core.translation.m2m100_engine import M2M100TranslationEngine
from core.translation.opus_mt_engine import OpusMTTranslationEngine
from schemas.model import ModelDescriptor


def build_translation_engine(descriptor: ModelDescriptor) -> BaseTranslationEngine:
    family = descriptor.family.lower()
    provider = descriptor.provider.lower()

    if family == "identity" and provider == "identity":
        return IdentityTranslationEngine(model_name=descriptor.model_name)

    common_kwargs = dict(
        model_name=descriptor.model_name,
        model_path=descriptor.model_path,
        download_root=descriptor.download_root,
        local_files_only=descriptor.local_files_only,
        source_language=descriptor.source_language,
        target_language=descriptor.target_language or "en",
        cpu_threads=descriptor.cpu_threads or 0,
        max_length=descriptor.max_length or 256,
        device=descriptor.device or "auto",
    )

    if family == "m2m100" and provider == "transformers":
        return M2M100TranslationEngine(**common_kwargs)

    if family == "opus_mt" and provider == "transformers":
        return OpusMTTranslationEngine(**common_kwargs)

    raise ValueError(
        "Unsupported translation runtime: "
        f"family={descriptor.family} provider={descriptor.provider}"
    )
