import pytest

from locaforge.domain.entry import EntryStatus, TranslationEntry


def make_entry(**changes: object) -> TranslationEntry:
    values: dict[str, object] = {
        "id": "entry-1",
        "key_path": ("dialog", "greeting"),
        "source": "Hello",
    }
    values.update(changes)
    return TranslationEntry(**values)  # type: ignore[arg-type]


def test_manual_translation_requires_review() -> None:
    entry = make_entry()

    entry.set_translation("Привет")

    assert entry.translation == "Привет"
    assert entry.status is EntryStatus.NEEDS_REVIEW


def test_locked_entry_cannot_be_changed() -> None:
    entry = make_entry(translation="Привет", status=EntryStatus.TRANSLATED, locked=True)

    with pytest.raises(ValueError, match="locked"):
        entry.set_translation("Здравствуйте")


def test_untranslated_entry_cannot_be_approved() -> None:
    with pytest.raises(ValueError, match="untranslated"):
        make_entry().approve()


def test_approved_entry_can_be_reopened_for_review() -> None:
    entry = make_entry(translation="Привет", status=EntryStatus.TRANSLATED)

    entry.approve()
    entry.reopen_review()

    assert entry.status is EntryStatus.NEEDS_REVIEW


def test_translated_entry_can_be_locked_and_unlocked() -> None:
    entry = make_entry(translation="Привет", status=EntryStatus.TRANSLATED)

    entry.set_locked(True)
    assert entry.locked is True
    entry.set_locked(False)
    assert entry.locked is False


def test_untranslated_entry_cannot_be_locked() -> None:
    with pytest.raises(ValueError, match="untranslated"):
        make_entry().set_locked(True)
