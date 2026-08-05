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
