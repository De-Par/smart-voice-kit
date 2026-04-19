from __future__ import annotations

import re
from dataclasses import dataclass

LANGUAGE_ALIASES = {
    "eng": "en",
    "english": "en",
    "rus": "ru",
    "russian": "ru",
    "swe": "sv",
    "swedish": "sv",
    "ukr": "uk",
    "ukrainian": "uk",
}


class LanguageDetectionError(RuntimeError):
    """Raised when transcript language cannot be determined reliably."""


@dataclass(frozen=True)
class ScriptProfile:
    latin: int = 0
    cyrillic: int = 0


@dataclass(frozen=True)
class LanguageSpanAnalysis:
    text: str
    kind: str = "text"
    language: str | None = None
    language_source: str = "unknown"


TOKEN_PATTERN = re.compile(r"\s+|[^\W_]+(?:[-'][^\W_]+)*|[^\w\s]+|_", re.UNICODE)
WORD_PATTERN = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)


def normalize_language_code(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip().lower()
    if not normalized:
        return None

    normalized = normalized.replace("_", "-")
    if normalized in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[normalized]

    primary_subtag = normalized.split("-", maxsplit=1)[0]
    return LANGUAGE_ALIASES.get(primary_subtag, primary_subtag)


def detect_text_language(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        raise LanguageDetectionError("Transcript is empty.")

    if _count_letters(normalized) < 6:
        raise LanguageDetectionError(
            "Transcript is too short for reliable language detection. Specify the language."
        )

    script_profile = _build_script_profile(normalized)
    if _is_mixed_script(script_profile):
        raise LanguageDetectionError(
            "Transcript contains mixed scripts. Specify the language explicitly."
        )

    try:
        from langdetect import DetectorFactory, LangDetectException, detect_langs
    except ImportError as error:
        raise LanguageDetectionError(
            "Language detection runtime is not installed. Reinstall with translation extras."
        ) from error

    DetectorFactory.seed = 0

    try:
        candidates = detect_langs(normalized)
    except LangDetectException as error:
        raise LanguageDetectionError(
            "Could not detect transcript language. Specify the language explicitly."
        ) from error

    normalized_candidates: list[tuple[str, float]] = []
    for candidate in candidates:
        language_code = normalize_language_code(candidate.lang)
        if language_code is None:
            continue
        normalized_candidates.append((language_code, float(candidate.prob)))

    if not normalized_candidates:
        raise LanguageDetectionError(
            "Could not detect transcript language. Specify the language explicitly."
        )

    best_language, best_probability = normalized_candidates[0]
    if best_probability < 0.80:
        raise LanguageDetectionError(
            "Transcript language is ambiguous. Specify the language explicitly."
        )

    if len(normalized_candidates) > 1:
        _, second_probability = normalized_candidates[1]
        if best_probability - second_probability < 0.20:
            raise LanguageDetectionError(
                "Transcript language is ambiguous. Specify the language explicitly."
            )

    return best_language


def analyze_text_language_spans(text: str) -> list[LanguageSpanAnalysis]:
    spans: list[LanguageSpanAnalysis] = []
    phrase_tokens: list[str] = []

    for token in TOKEN_PATTERN.findall(text):
        if WORD_PATTERN.fullmatch(token):
            phrase_tokens.append(token)
            continue

        if token.isspace():
            if phrase_tokens:
                phrase_tokens.append(token)
            else:
                spans.append(
                    LanguageSpanAnalysis(text=token, kind="literal", language_source="literal")
                )
            continue

        if phrase_tokens:
            spans.extend(_analyze_phrase("".join(phrase_tokens)))
            phrase_tokens = []
        spans.append(LanguageSpanAnalysis(text=token, kind="literal", language_source="literal"))

    if phrase_tokens:
        spans.extend(_analyze_phrase("".join(phrase_tokens)))

    return [span for span in spans if span.text]


def detect_text_script(text: str) -> str:
    return _script_label(text)


def _analyze_phrase(text: str) -> list[LanguageSpanAnalysis]:
    stripped = text.strip()
    if not stripped:
        return [LanguageSpanAnalysis(text=text, kind="literal", language_source="literal")]

    script_profile = _build_script_profile(stripped)
    if _is_mixed_script(script_profile):
        return _split_phrase_by_script(text)

    try:
        language = detect_text_language(stripped)
    except LanguageDetectionError:
        return [
            LanguageSpanAnalysis(
                text=text,
                kind="text",
                language=None,
                language_source="unknown",
            )
        ]

    return [
        LanguageSpanAnalysis(
            text=text,
            kind="text",
            language=language,
            language_source="detected",
        )
    ]


def _split_phrase_by_script(text: str) -> list[LanguageSpanAnalysis]:
    spans: list[LanguageSpanAnalysis] = []
    current_tokens: list[str] = []
    current_script: str | None = None

    for token in TOKEN_PATTERN.findall(text):
        if token.isspace():
            if current_tokens:
                current_tokens.append(token)
            else:
                spans.append(
                    LanguageSpanAnalysis(text=token, kind="literal", language_source="literal")
                )
            continue

        token_script = _script_label(token)
        if token_script in {"latin", "cyrillic"}:
            if current_tokens and current_script not in {None, token_script}:
                spans.extend(_analyze_phrase("".join(current_tokens)))
                current_tokens = []
            current_tokens.append(token)
            current_script = token_script
            continue

        if current_tokens:
            current_tokens.append(token)
        else:
            spans.append(
                LanguageSpanAnalysis(text=token, kind="literal", language_source="literal")
            )

    if current_tokens:
        spans.extend(_analyze_phrase("".join(current_tokens)))

    return spans


def _build_script_profile(text: str) -> ScriptProfile:
    latin = 0
    cyrillic = 0
    for char in text.lower():
        codepoint = ord(char)
        if 0x0400 <= codepoint <= 0x04FF:
            cyrillic += 1
        elif ("a" <= char <= "z") or char in {"å", "ä", "ö"}:
            latin += 1
    return ScriptProfile(latin=latin, cyrillic=cyrillic)


def _count_letters(text: str) -> int:
    return sum(1 for char in text if char.isalpha())


def _script_label(text: str) -> str:
    profile = _build_script_profile(text)
    if profile.cyrillic and not profile.latin:
        return "cyrillic"
    if profile.latin and not profile.cyrillic:
        return "latin"
    if profile.latin and profile.cyrillic:
        return "mixed"
    return "other"


def _is_mixed_script(profile: ScriptProfile) -> bool:
    if profile.latin < 3 or profile.cyrillic < 3:
        return False
    dominant = max(profile.latin, profile.cyrillic)
    secondary = min(profile.latin, profile.cyrillic)
    return secondary / dominant >= 0.35
