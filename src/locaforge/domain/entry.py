"""Translation entry entity and its state rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

type JsonPathPart = str | int
type JsonPath = tuple[JsonPathPart, ...]


class EntryStatus(StrEnum):
    UNTRANSLATED = "untranslated"
    TRANSLATED = "translated"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    ERROR = "error"


@dataclass(slots=True)
class TranslationEntry:
    """A source string and its editable translation within a project."""

    id: str
    key_path: JsonPath
    source: str
    translation: str | None = None
    status: EntryStatus = EntryStatus.UNTRANSLATED
    locked: bool = False
    context: str | None = None
    max_length: int | None = None
    placeholders: tuple[str, ...] = field(default_factory=tuple)
    key: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("TranslationEntry.id must not be empty")
        if not self.key_path:
            raise ValueError("TranslationEntry.key_path must not be empty")
        if self.max_length is not None and self.max_length < 1:
            raise ValueError("TranslationEntry.max_length must be positive")
        if self.locked and self.status is EntryStatus.UNTRANSLATED:
            raise ValueError("An untranslated entry cannot be locked")

    @property
    def is_translated(self) -> bool:
        return self.translation is not None

    def set_translation(self, translation: str | None) -> None:
        """Apply a manual edit while preserving the review workflow."""
        if self.locked:
            raise ValueError("A locked translation entry cannot be changed")

        self.translation = translation
        self.status = (
            EntryStatus.NEEDS_REVIEW if translation is not None else EntryStatus.UNTRANSLATED
        )

    def approve(self) -> None:
        if self.translation is None:
            raise ValueError("An untranslated entry cannot be approved")
        self.status = EntryStatus.APPROVED

    def reopen_review(self) -> None:
        if self.translation is None:
            raise ValueError("An untranslated entry cannot be reviewed")
        self.status = EntryStatus.NEEDS_REVIEW

    def set_locked(self, locked: bool) -> None:
        if locked and self.translation is None:
            raise ValueError("An untranslated entry cannot be locked")
        self.locked = locked

    def mark_model_translation(self, translation: str) -> None:
        """Store a validated model result without approving it."""
        if self.locked:
            raise ValueError("A locked translation entry cannot be changed")
        self.translation = translation
        self.status = EntryStatus.TRANSLATED

    def mark_error(self) -> None:
        self.status = EntryStatus.ERROR
