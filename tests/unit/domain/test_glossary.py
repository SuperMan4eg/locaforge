from __future__ import annotations

import pytest

from locaforge.domain.glossary import GlossaryTerm


@pytest.mark.parametrize(
    "values",
    [
        ("", "ru", "Save", "Сохранить"),
        ("en", " ", "Save", "Сохранить"),
        ("en", "ru", "", "Сохранить"),
        ("en", "ru", "Save", " "),
    ],
)
def test_glossary_term_rejects_empty_required_values(
    values: tuple[str, str, str, str],
) -> None:
    with pytest.raises(ValueError):
        GlossaryTerm(*values)
