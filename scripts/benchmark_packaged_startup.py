"""Compare startup latency and footprint of packaged LocaForge variants."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path


def _percentile(samples: Sequence[float], percentile: float) -> float:
    ordered = sorted(samples)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(executable: Path, argument: str, environment: dict[str, str]) -> float:
    started = time.perf_counter_ns()
    completed = subprocess.run(
        [executable, argument],
        check=False,
        capture_output=True,
        env=environment,
        timeout=60,
    )
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    if completed.returncode != 0:
        raise RuntimeError(
            f"{executable.name} {argument} failed with exit code {completed.returncode}"
        )
    return elapsed_ms


def _measure(
    label: str,
    executable: Path,
    *,
    warmups: int,
    iterations: int,
) -> dict[str, object]:
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    _run(executable, "--self-test", environment)
    for _ in range(warmups):
        _run(executable, "--smoke-test", environment)
    samples = [
        _run(executable, "--smoke-test", environment) for _ in range(iterations)
    ]
    return {
        "label": label,
        "executable": str(executable.resolve()),
        "sha256": _sha256(executable),
        "distribution_bytes": _directory_size(executable.parent),
        "iterations": iterations,
        "startup_median_ms": round(statistics.median(samples), 6),
        "startup_p95_ms": round(_percentile(samples, 0.95), 6),
        "startup_minimum_ms": round(min(samples), 6),
        "startup_maximum_ms": round(max(samples), 6),
        "samples_ms": [round(sample, 6) for sample in samples],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        action="append",
        required=True,
        metavar="LABEL=PATH",
    )
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    if args.warmups < 0 or args.iterations < 1:
        raise SystemExit("warmups cannot be negative and iterations must be positive")

    candidates: list[tuple[str, Path]] = []
    for raw_candidate in args.candidate:
        label, separator, raw_path = raw_candidate.partition("=")
        executable = Path(raw_path)
        if not separator or not label or not executable.is_file():
            raise SystemExit(f"invalid candidate: {raw_candidate!r}")
        candidates.append((label, executable))

    report = {
        "warmups": args.warmups,
        "iterations": args.iterations,
        "results": [
            _measure(label, executable, warmups=args.warmups, iterations=args.iterations)
            for label, executable in candidates
        ],
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
