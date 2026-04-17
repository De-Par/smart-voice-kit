from __future__ import annotations

from core.translation.transformers_provider import BaseTransformersTranslationEngine


class M2M100TranslationEngine(BaseTransformersTranslationEngine):
    family_name = "m2m100"

    def build_generate_kwargs(
        self,
        *,
        tokenizer,
        source_language: str | None,
        target_language: str,
    ) -> dict[str, int]:
        if source_language and hasattr(tokenizer, "src_lang"):
            tokenizer.src_lang = source_language
        if hasattr(tokenizer, "get_lang_id"):
            return {"forced_bos_token_id": tokenizer.get_lang_id(target_language)}
        return {}
