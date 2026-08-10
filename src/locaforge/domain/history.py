"""Translation revision domain values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EntryRevision:
    """A previous translation value stored before an edit."""

    revision_id: int
    entry_id: str
    translation: str | None
    recorded_at: datetime

    def __post_init__(self) -> None:
        if self.revision_id < 1:
            raise ValueError("Revision id must be positive")
        if not self.entry_id:
            raise ValueError("Revision entry id must not be empty")


@dataclass(frozen=True, slots=True)
class ProjectOperation:
    """A persistent project operation available to Undo or Redo."""

    operation_id: int
    label: str
    recorded_at: datetime
    undone: bool
    entry_count: int

    def __post_init__(self) -> None:
        if self.operation_id < 1:
            raise ValueError("Operation id must be positive")
        if not self.label:
            raise ValueError("Operation label must not be empty")
        if self.entry_count < 1:
            raise ValueError("Operation entry count must be positive")
