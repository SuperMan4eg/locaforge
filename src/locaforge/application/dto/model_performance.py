"""Privacy-safe timing and token metrics reported by model backends."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelUsageMetrics:
    """Metrics for one completed model request, using Ollama's native units."""

    total_duration_ns: int = 0
    load_duration_ns: int = 0
    prompt_eval_count: int = 0
    prompt_eval_duration_ns: int = 0
    eval_count: int = 0
    eval_duration_ns: int = 0

    @property
    def generation_tokens_per_second(self) -> float:
        if self.eval_duration_ns <= 0:
            return 0.0
        return self.eval_count * 1_000_000_000 / self.eval_duration_ns

@dataclass(frozen=True, slots=True)
class ModelPerformanceSnapshot:
    """Aggregate metrics collected since the active model client was created."""

    request_count: int = 0
    total_duration_ns: int = 0
    load_duration_ns: int = 0
    prompt_eval_count: int = 0
    prompt_eval_duration_ns: int = 0
    eval_count: int = 0
    eval_duration_ns: int = 0

    @property
    def generation_tokens_per_second(self) -> float:
        if self.eval_duration_ns <= 0:
            return 0.0
        return self.eval_count * 1_000_000_000 / self.eval_duration_ns
