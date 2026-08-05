from locaforge.presentation.translation_length import format_translation_length


def test_formats_length_without_a_limit() -> None:
    assert format_translation_length(12, None) == "Characters: 12"


def test_formats_length_with_limit_and_overflow() -> None:
    assert format_translation_length(3, 5) == "Characters: 3 / 5"
    assert format_translation_length(6, 5) == "Characters: 6 / 5 — limit exceeded"
