from __future__ import annotations

from core.language import (
    analyze_text_language_spans,
    normalize_language_code,
)
from schemas.command import (
    CommandNormalizationResult,
    CommandSource,
    CommandSpan,
    NormalizedCommand,
)
from services.translation_router import TranslationRouter


class SpanNormalizationService:
    def __init__(self, translation_router: TranslationRouter) -> None:
        self.translation_router = translation_router

    def normalize(
        self,
        text: str,
        *,
        modality: str,
        target_language: str,
    ) -> CommandNormalizationResult:
        analyzed_spans = analyze_text_language_spans(text)
        command_spans: list[CommandSpan] = []
        normalized_parts: list[str] = []
        translated_count = 0
        preserved_count = 0
        translation_seconds = 0.0
        translatable_span_count = 0
        untranslated_span_count = 0

        for span in analyzed_spans:
            if span.kind == "literal":
                command_spans.append(
                    CommandSpan(
                        text=span.text,
                        kind="literal",
                        language_source="literal",
                        status="literal",
                        normalized_text=span.text,
                    )
                )
                normalized_parts.append(span.text)
                continue

            translation_candidates = self.iter_language_candidates(
                span_language=span.language,
                span_text=span.text,
                target_language=target_language,
            )
            if not translation_candidates:
                command_spans.append(
                    CommandSpan(
                        text=span.text,
                        kind="text",
                        language=None,
                        language_source=span.language_source,
                        status="preserved",
                        normalized_text=span.text,
                    )
                )
                normalized_parts.append(span.text)
                preserved_count += 1
                continue

            if translation_candidates[0][0] == target_language:
                command_spans.append(
                    CommandSpan(
                        text=span.text,
                        kind="text",
                        language=translation_candidates[0][0],
                        language_source=translation_candidates[0][1],
                        status="kept",
                        normalized_text=span.text,
                    )
                )
                normalized_parts.append(span.text)
                preserved_count += 1
                continue

            translatable_span_count += 1
            translation = None
            selected_language = None
            selected_language_source = span.language_source
            for candidate_language, candidate_source in translation_candidates:
                if candidate_language == target_language:
                    continue
                try:
                    translation = self.translation_router.translate(
                        span.text.strip(),
                        source_language=candidate_language,
                        target_language=target_language,
                    )
                except RuntimeError:
                    continue
                selected_language = candidate_language
                selected_language_source = candidate_source
                break

            if translation is None or selected_language is None:
                untranslated_span_count += 1
                command_spans.append(
                    CommandSpan(
                        text=span.text,
                        kind="text",
                        language=translation_candidates[0][0],
                        language_source=translation_candidates[0][1],
                        status="preserved",
                        normalized_text=span.text,
                    )
                )
                normalized_parts.append(span.text)
                preserved_count += 1
                continue

            normalized_text = restore_surrounding_whitespace(span.text, translation.text)
            command_spans.append(
                CommandSpan(
                    text=span.text,
                    kind="text",
                    language=selected_language,
                    language_source=selected_language_source,
                    status="translated",
                    normalized_text=normalized_text,
                    translation_family=translation.translation_family,
                    translation_provider=translation.translation_provider,
                    translation_model_name=translation.model_name,
                )
            )
            normalized_parts.append(normalized_text)
            translated_count += 1
            translation_seconds += translation.inference_seconds

        normalized_text = "".join(normalized_parts).strip() or text
        first_translated_span = next(
            (span for span in command_spans if span.status == "translated"),
            None,
        )
        status, message = summarize_partial_normalization(
            translated_count=translated_count,
            preserved_count=preserved_count,
            translatable_span_count=translatable_span_count,
            untranslated_span_count=untranslated_span_count,
        )
        return CommandNormalizationResult(
            source=CommandSource(
                text=text,
                modality=modality,
                language=None,
                language_source="segmented",
            ),
            normalized=NormalizedCommand(
                text=normalized_text,
                target_language=target_language,
                status=status,
                message=message,
                translated_span_count=translated_count,
                preserved_span_count=preserved_count,
                translation_family=(
                    first_translated_span.translation_family
                    if first_translated_span is not None
                    else None
                ),
                translation_provider=(
                    first_translated_span.translation_provider
                    if first_translated_span is not None
                    else None
                ),
                translation_model_name=(
                    first_translated_span.translation_model_name
                    if first_translated_span is not None
                    else None
                ),
                translation_inference_seconds=translation_seconds or None,
            ),
            spans=command_spans,
        )

    def iter_language_candidates(
        self,
        *,
        span_language: str | None,
        span_text: str,
        target_language: str,
    ) -> list[tuple[str, str]]:
        candidates: list[tuple[str, str]] = []
        seen: set[str] = set()

        def add(language: str | None, source: str) -> None:
            normalized_language = normalize_language_code(language)
            if normalized_language is None or normalized_language in seen:
                return
            candidates.append((normalized_language, source))
            seen.add(normalized_language)

        add(span_language, "detected")

        return candidates


def restore_surrounding_whitespace(source_text: str, translated_text: str) -> str:
    leading = source_text[: len(source_text) - len(source_text.lstrip())]
    trailing = source_text[len(source_text.rstrip()) :]
    return f"{leading}{translated_text.strip()}{trailing}"


def summarize_partial_normalization(
    *,
    translated_count: int,
    preserved_count: int,
    translatable_span_count: int,
    untranslated_span_count: int,
) -> tuple[str, str | None]:
    if translated_count > 0 and untranslated_span_count == 0 and preserved_count == 0:
        return "translated", "Translated command span by span."
    if translated_count > 0:
        return "partial", "Partially normalized command; unsupported spans were preserved."
    if translatable_span_count == 0 and preserved_count > 0:
        return "skipped", "No translatable spans were detected."
    return "error", "No supported spans could be normalized."
