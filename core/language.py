from __future__ import annotations

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
