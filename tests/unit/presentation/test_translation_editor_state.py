import pytest

from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.presentation.translation_editor_state import TranslationEditorState


def make_entry(
    *,
    status: EntryStatus = EntryStatus.TRANSLATED,
    translation: str | None = "Привет",
    locked: bool = False,
    model_translation: str | None = "Модель",
    reviewer_translation: str | None = "Ревьюер",
) -> TranslationEntry:
    return TranslationEntry(
        id="entry-1",
        key_path=("hello",),
        source="Hello",
        translation=translation,
        status=status,
        locked=locked,
        max_length=20,
        model_translation=model_translation,
        reviewer_translation=reviewer_translation,
    )


def test_editable_translated_entry_exposes_content_and_actions() -> None:
    state = TranslationEditorState.from_entry(make_entry(), busy=False)

    assert state.entry_id == "entry-1"
    assert state.max_length == 20
    assert state.source_text == "Hello"
    assert state.translation_text == "Привет"
    assert state.model_candidate_text == "Модель"
    assert state.reviewer_candidate_text == "Ревьюер"
    assert state.model_candidate_enabled is True
    assert state.reviewer_candidate_enabled is True
    assert state.editor_read_only is False
    assert state.copy_source_enabled is True
    assert state.apply_enabled is True
    assert state.approval_text == "Approve"
    assert state.approval_enabled is True
    assert state.lock_checked is False
    assert state.lock_enabled is True


def test_empty_state_resets_all_editor_fields_and_actions() -> None:
    state = TranslationEditorState.empty()

    assert state.entry_id is None
    assert state.locked is False
    assert state.max_length is None
    assert state.source_text == ""
    assert state.translation_text == ""
    assert state.model_candidate_text == ""
    assert state.reviewer_candidate_text == ""
    assert state.model_candidate_enabled is False
    assert state.reviewer_candidate_enabled is False
    assert state.editor_read_only is False
    assert state.copy_source_enabled is False
    assert state.apply_enabled is False
    assert state.approval_text == "Approve"
    assert state.approval_enabled is False
    assert state.lock_checked is False
    assert state.lock_enabled is False


def test_untranslated_entry_uses_empty_text_and_disables_approval_and_lock() -> None:
    state = TranslationEditorState.from_entry(
        make_entry(
            status=EntryStatus.UNTRANSLATED,
            translation=None,
            model_translation=None,
            reviewer_translation=None,
        ),
        busy=False,
    )

    assert state.translation_text == ""
    assert state.model_candidate_text == ""
    assert state.reviewer_candidate_text == ""
    assert state.model_candidate_enabled is False
    assert state.reviewer_candidate_enabled is False
    assert state.approval_enabled is False
    assert state.lock_enabled is False


def test_approved_entry_uses_reopen_action() -> None:
    state = TranslationEditorState.from_entry(
        make_entry(status=EntryStatus.APPROVED), busy=False
    )

    assert state.approval_text == "Reopen review"
    assert state.approval_enabled is True


def test_error_entry_cannot_be_approved() -> None:
    state = TranslationEditorState.from_entry(
        make_entry(status=EntryStatus.ERROR), busy=False
    )

    assert state.approval_text == "Approve"
    assert state.approval_enabled is False


def test_locked_entry_is_read_only_but_can_be_unlocked() -> None:
    state = TranslationEditorState.from_entry(make_entry(locked=True), busy=False)

    assert state.locked is True
    assert state.editor_read_only is True
    assert state.copy_source_enabled is False
    assert state.apply_enabled is False
    assert state.model_candidate_enabled is False
    assert state.reviewer_candidate_enabled is False
    assert state.lock_checked is True
    assert state.lock_enabled is True


@pytest.mark.parametrize("status", list(EntryStatus))
def test_busy_state_disables_all_mutating_actions(status: EntryStatus) -> None:
    translation = None if status is EntryStatus.UNTRANSLATED else "Привет"
    entry = make_entry(
        status=status,
        translation=translation,
        locked=False,
    )

    state = TranslationEditorState.from_entry(entry, busy=True)

    assert state.copy_source_enabled is False
    assert state.apply_enabled is False
    assert state.model_candidate_enabled is False
    assert state.reviewer_candidate_enabled is False
    assert state.approval_enabled is False
    assert state.lock_enabled is False
