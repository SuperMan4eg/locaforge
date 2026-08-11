"""Derive translation editor widget state from one domain entry."""

from __future__ import annotations

from dataclasses import dataclass

from locaforge.domain.entry import EntryStatus, TranslationEntry


@dataclass(frozen=True, slots=True)
class TranslationEditorState:
    entry_id: str | None
    locked: bool
    max_length: int | None
    source_text: str
    translation_text: str
    model_candidate_text: str
    reviewer_candidate_text: str
    model_candidate_enabled: bool
    reviewer_candidate_enabled: bool
    editor_read_only: bool
    copy_source_enabled: bool
    apply_enabled: bool
    approval_text: str
    approval_enabled: bool
    lock_checked: bool
    lock_enabled: bool

    @classmethod
    def empty(cls) -> TranslationEditorState:
        return cls(
            entry_id=None,
            locked=False,
            max_length=None,
            source_text="",
            translation_text="",
            model_candidate_text="",
            reviewer_candidate_text="",
            model_candidate_enabled=False,
            reviewer_candidate_enabled=False,
            editor_read_only=False,
            copy_source_enabled=False,
            apply_enabled=False,
            approval_text="Approve",
            approval_enabled=False,
            lock_checked=False,
            lock_enabled=False,
        )

    @classmethod
    def from_entry(cls, entry: TranslationEntry, *, busy: bool) -> TranslationEditorState:
        editable = not entry.locked and not busy
        return cls(
            entry_id=entry.id,
            locked=entry.locked,
            max_length=entry.max_length,
            source_text=entry.source,
            translation_text=entry.translation or "",
            model_candidate_text=entry.model_translation or "",
            reviewer_candidate_text=entry.reviewer_translation or "",
            model_candidate_enabled=entry.model_translation is not None and editable,
            reviewer_candidate_enabled=entry.reviewer_translation is not None and editable,
            editor_read_only=entry.locked,
            copy_source_enabled=editable,
            apply_enabled=editable,
            approval_text=(
                "Reopen review" if entry.status is EntryStatus.APPROVED else "Approve"
            ),
            approval_enabled=(
                not busy
                and entry.translation is not None
                and (
                    entry.status is EntryStatus.APPROVED
                    or entry.status is not EntryStatus.ERROR
                )
            ),
            lock_checked=entry.locked,
            lock_enabled=not busy and entry.translation is not None,
        )
