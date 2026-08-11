"""Compare CPython and isolated Cython implementations of consistency validation."""

from __future__ import annotations

import argparse
import importlib
import json
import statistics
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from locaforge.application.services.consistency_validator import ConsistencyValidator
from locaforge.domain.entry import TranslationEntry


def _entries(size: int) -> tuple[TranslationEntry, ...]:
    return tuple(
        TranslationEntry(
            id=f"entry-{index}",
            key_path=("messages", index),
            source=f"Repeated source {index % 1_000}",
            translation=f"Translation {(index + index // 1_000) % 2}",
        )
        for index in range(size)
    )


def _measure(action: Callable[[], object], warmups: int, iterations: int) -> list[float]:
    for _ in range(warmups):
        action()
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        action()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return samples


def _summary(samples: Sequence[float]) -> dict[str, float]:
    return {
        "median_ms": round(statistics.median(samples), 6),
        "minimum_ms": round(min(samples), 6),
        "maximum_ms": round(max(samples), 6),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extension-dir", type=Path, required=True)
    parser.add_argument("--size", type=int, default=50_000)
    parser.add_argument("--warmups", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    if args.size < 1 or args.iterations < 1 or args.warmups < 0:
        raise SystemExit("size and iterations must be positive; warmups cannot be negative")

    sys.path.insert(0, str(args.extension_dir.resolve()))
    compiled_module = importlib.import_module("stage7_consistency_validator")
    compiled_validator = compiled_module.ConsistencyValidator()
    python_validator = ConsistencyValidator()
    entries = _entries(args.size)

    python_samples = _measure(
        lambda: python_validator.validate(entries), args.warmups, args.iterations
    )
    cython_samples = _measure(
        lambda: compiled_validator.validate(entries), args.warmups, args.iterations
    )
    python_summary = _summary(python_samples)
    cython_summary = _summary(cython_samples)
    speedup = python_summary["median_ms"] / cython_summary["median_ms"]
    report = {
        "size": args.size,
        "warmups": args.warmups,
        "iterations": args.iterations,
        "python": python_summary,
        "cython": cython_summary,
        "speedup": round(speedup, 6),
    }
    encoded = json.dumps(report, indent=2) + "\n"
    if args.json is None:
        print(encoded, end="")
    else:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
