from __future__ import annotations

from core.translation.transformers_provider import BaseTransformersTranslationEngine


class OpusMTTranslationEngine(BaseTransformersTranslationEngine):
    family_name = "opus_mt"

    def validate_language_pair(
        self,
        *,
        source_language: str | None,
        target_language: str,
    ) -> None:
        if source_language is None:
            return

        marker = "opus-mt-"
        normalized_source = source_language.lower()
        normalized_target = target_language.lower()
        model_name = self.model_name.lower()
        if marker not in model_name:
            return

        language_pair = model_name.split(marker, maxsplit=1)[1].split("/", maxsplit=1)[0]
        parts = language_pair.split("-")
        if len(parts) < 2:
            return

        expected_source = parts[-2]
        expected_target = parts[-1]
        if (normalized_source, normalized_target) != (expected_source, expected_target):
            raise RuntimeError(
                "Configured OPUS-MT model does not match the requested language pair "
                f"{normalized_source}->{normalized_target}."
            )

    def build_generate_kwargs(
        self,
        *,
        tokenizer,
        source_language: str | None,
        target_language: str,
    ) -> dict[str, int]:
        return {}
