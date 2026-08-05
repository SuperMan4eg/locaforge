from locaforge.application.services.translation_validator import (
    TranslationValidator,
    ValidationCode,
)
from locaforge.domain.entry import TranslationEntry


def make_entry(source: str = "Hello", max_length: int | None = None) -> TranslationEntry:
    return TranslationEntry("entry-1", ("text",), source, max_length=max_length)


def test_accepts_a_structurally_valid_translation() -> None:
    issues = TranslationValidator().validate(make_entry("Hello\nWorld"), "Привет\nМир")

    assert not issues


def test_reports_empty_length_and_line_break_issues() -> None:
    validator = TranslationValidator()

    empty_issues = validator.validate(make_entry(), "   ")
    long_issues = validator.validate(make_entry(max_length=3), "Привет")
    line_break_issues = validator.validate(make_entry("Hello\nWorld"), "Привет, мир")

    assert empty_issues[0].code is ValidationCode.EMPTY_TRANSLATION
    assert long_issues[0].code is ValidationCode.MAX_LENGTH_EXCEEDED
    assert line_break_issues[0].code is ValidationCode.LINE_BREAK_MISMATCH


def test_reports_invalid_unicode_and_control_characters() -> None:
    issues = TranslationValidator().validate(make_entry(), "Привет\ud800\x00")

    assert {issue.code for issue in issues} == {
        ValidationCode.INVALID_UNICODE,
        ValidationCode.CONTROL_CHARACTER,
    }


def test_reports_chinese_characters_in_english_translation() -> None:
    issues = TranslationValidator().validate(make_entry(), "Save 是", "en")

    assert [issue.code for issue in issues] == [ValidationCode.TARGET_LANGUAGE_MISMATCH]


def test_reports_japanese_and_korean_characters_in_russian_translation() -> None:
    japanese_issues = TranslationValidator().validate(make_entry(), "テスト", "ru")
    korean_issues = TranslationValidator().validate(make_entry(), "테스트", "ru")

    assert [issue.code for issue in japanese_issues] == [
        ValidationCode.TARGET_LANGUAGE_MISMATCH
    ]
    assert [issue.code for issue in korean_issues] == [
        ValidationCode.TARGET_LANGUAGE_MISMATCH
    ]


def test_reports_unchanged_substantial_source_text() -> None:
    issues = TranslationValidator().validate(make_entry("Save game"), "Save game", "ru")

    assert [issue.code for issue in issues] == [ValidationCode.SOURCE_TEXT_UNCHANGED]


def test_allows_short_identical_tokens() -> None:
    issues = TranslationValidator().validate(make_entry("OK"), "OK", "ru")

    assert not issues
