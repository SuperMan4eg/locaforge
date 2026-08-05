from __future__ import annotations

import pytest

from locaforge.domain.translation_memory import (
    TranslationMemoryMatch,
    TranslationMemoryRecord,
)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_language", " "),
        ("target_language", ""),
        ("source", ""),
        ("translation", ""),
    ],
)
def test_translation_memory_record_rejects_empty_required_values(
    field: str, value: str
) -> None:
    values = {
        "source_language": "en",
        "target_language": "ru",
        "source": "Play",
        "translation": "Играть",
    }
    values[field] = value

    with pytest.raises(ValueError):
        TranslationMemoryRecord(**values)


@pytest.mark.parametrize("score", [-0.01, 1.01])
def test_translation_memory_match_rejects_invalid_score(score: float) -> None:
    record = TranslationMemoryRecord("en", "ru", "Play", "Играть")

    with pytest.raises(ValueError):
        TranslationMemoryMatch(record, score)
