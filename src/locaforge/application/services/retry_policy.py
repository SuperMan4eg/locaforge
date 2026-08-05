"""Retry configuration for batch translation fallback."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BatchRetryPolicy:
    attempts_per_group: int = 2

    def __post_init__(self) -> None:
        if self.attempts_per_group < 1:
            raise ValueError("attempts_per_group must be positive")
