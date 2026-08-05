from __future__ import annotations

from locaforge.application.dto.validation import ValidationCode
from locaforge.application.services.glossary_validator import GlossaryValidator
from locaforge.domain.glossary import GlossaryTerm


def test_glossary_validator_accepts_required_target_term() -> None:
    term = GlossaryTerm("en", "ru", "Save", "Сохранить")

    issues = GlossaryValidator().validate(
        "Save the game", "Сохранить игру", (term,)
    )

    assert issues == ()


def test_glossary_validator_reports_missing_required_target() -> None:
    term = GlossaryTerm("en", "ru", "Save", "Сохранить")

    issues = GlossaryValidator().validate("Save the game", "Записать игру", (term,))

    assert len(issues) == 1
    assert issues[0].code is ValidationCode.GLOSSARY_MISMATCH


def test_glossary_validator_ignores_term_absent_from_source() -> None:
    term = GlossaryTerm("en", "ru", "Exit", "Выход")

    issues = GlossaryValidator().validate("Save the game", "Записать игру", (term,))

    assert issues == ()
