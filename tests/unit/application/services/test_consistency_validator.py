from locaforge.application.dto.validation import ValidationCode
from locaforge.application.services.consistency_validator import ConsistencyValidator
from locaforge.domain.entry import TranslationEntry


def test_reports_every_entry_with_different_translations_for_same_source() -> None:
    entries = (
        TranslationEntry("one", ("one",), "Save", translation="Сохранить"),
        TranslationEntry("two", ("two",), "Save", translation="Записать"),
        TranslationEntry("three", ("three",), "Cancel", translation="Отмена"),
    )

    issues = ConsistencyValidator().validate(entries)

    assert set(issues) == {"one", "two"}
    assert issues["one"][0].code is ValidationCode.INCONSISTENT_TRANSLATION
    assert "«Записать»" in issues["one"][0].message
    assert "«Сохранить»" in issues["one"][0].message


def test_keeps_contexts_separate() -> None:
    entries = (
        TranslationEntry(
            "one", ("one",), "Open", translation="Открыть", context="file"
        ),
        TranslationEntry(
            "two", ("two",), "Open", translation="Открыто", context="state"
        ),
    )

    assert ConsistencyValidator().validate(entries) == {}
