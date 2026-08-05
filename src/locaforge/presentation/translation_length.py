"""Formatting helpers for the translation editor length indicator."""


def format_translation_length(length: int, maximum: int | None) -> str:
    if maximum is None:
        return f"Characters: {length}"
    suffix = " — limit exceeded" if length > maximum else ""
    return f"Characters: {length} / {maximum}{suffix}"
