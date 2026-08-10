"""Messages exchanged with local translation reviewers."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReviewRequestItem:
    entry_id: str
    source: str
    translation: str


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    model: str
    source_language: str
    target_language: str
    entries: tuple[ReviewRequestItem, ...]
    timeout_seconds: float
    prompt: str = ""
    reasoning: str = "off"


@dataclass(frozen=True, slots=True)
class ReviewResult:
    entry_id: str
    issue: str | None
    suggested_translation: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewResponse:
    results: tuple[ReviewResult, ...]


@dataclass(frozen=True, slots=True)
class ReviewBatchResult:
    reviewed_entries: int
    issue_count: int
    cancelled: bool = False
