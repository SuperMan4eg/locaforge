"""Project-scoped model settings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_REVIEW_PROMPT = """Act as a localization reviewer.
Check meaning, completeness, terminology, placeholders, and natural target-language usage.
Report only clear problems. Do not suggest purely stylistic changes."""

REASONING_MODES = ("off", "low", "medium", "high")


@dataclass(frozen=True, slots=True)
class ModelSettings:
    model: str = "qwen3"
    timeout_seconds: float = 120.0
    batch_size: int = 5
    system_prompt: str = ""
    review_prompt: str = DEFAULT_REVIEW_PROMPT
    review_model: str = ""
    translation_reasoning: str = "off"
    review_reasoning: str = "off"
    keep_alive_seconds: int = 300

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("Model name must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("Model timeout must be positive")
        if self.batch_size < 1:
            raise ValueError("Batch size must be positive")
        if self.keep_alive_seconds < -1:
            raise ValueError("Model keep-alive must be -1 or a non-negative number of seconds")
        if self.review_model and not self.review_model.strip():
            raise ValueError("Reviewer model name must not be blank")
        if self.translation_reasoning not in REASONING_MODES:
            raise ValueError("Invalid translation reasoning mode")
        if self.review_reasoning not in REASONING_MODES:
            raise ValueError("Invalid reviewer reasoning mode")

    @property
    def effective_review_model(self) -> str:
        return self.review_model or self.model

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "batch_size": self.batch_size,
            "system_prompt": self.system_prompt,
            "review_prompt": self.review_prompt,
            "review_model": self.review_model,
            "translation_reasoning": self.translation_reasoning,
            "review_reasoning": self.review_reasoning,
            "keep_alive_seconds": self.keep_alive_seconds,
        }

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> ModelSettings:
        defaults = cls()
        model = values.get("model")
        timeout_seconds = values.get("timeout_seconds")
        batch_size = values.get("batch_size")
        system_prompt = values.get("system_prompt")
        review_prompt = values.get("review_prompt")
        review_model = values.get("review_model")
        translation_reasoning = values.get("translation_reasoning")
        review_reasoning = values.get("review_reasoning")
        keep_alive_seconds = values.get("keep_alive_seconds")
        return cls(
            model=model if isinstance(model, str) else defaults.model,
            timeout_seconds=(
                float(timeout_seconds)
                if isinstance(timeout_seconds, int | float)
                and not isinstance(timeout_seconds, bool)
                else defaults.timeout_seconds
            ),
            batch_size=(
                batch_size
                if isinstance(batch_size, int) and not isinstance(batch_size, bool)
                else defaults.batch_size
            ),
            system_prompt=(
                system_prompt if isinstance(system_prompt, str) else defaults.system_prompt
            ),
            review_prompt=(
                review_prompt if isinstance(review_prompt, str) else defaults.review_prompt
            ),
            review_model=(
                review_model if isinstance(review_model, str) else defaults.review_model
            ),
            translation_reasoning=(
                translation_reasoning
                if isinstance(translation_reasoning, str)
                and translation_reasoning in REASONING_MODES
                else defaults.translation_reasoning
            ),
            review_reasoning=(
                review_reasoning
                if isinstance(review_reasoning, str) and review_reasoning in REASONING_MODES
                else defaults.review_reasoning
            ),
            keep_alive_seconds=(
                keep_alive_seconds
                if isinstance(keep_alive_seconds, int)
                and not isinstance(keep_alive_seconds, bool)
                and keep_alive_seconds >= -1
                else defaults.keep_alive_seconds
            ),
        )
