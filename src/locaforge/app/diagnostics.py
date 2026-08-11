"""Privacy-preserving diagnostics for support reports."""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import qVersion

from locaforge import __version__ as locaforge_version
from locaforge.app.exception_handler import get_last_incident_id
from locaforge.application.dto.model_performance import ModelPerformanceSnapshot


@dataclass(frozen=True, slots=True)
class DiagnosticContext:
    ui_locale: str
    theme: str
    online_lookup_enabled: bool
    project_open: bool = False
    project_format_version: int | None = None
    document_count: int = 0
    entry_count: int = 0
    source_formats: tuple[str, ...] = ()
    project_dirty: bool = False
    model_performance: ModelPerformanceSnapshot = ModelPerformanceSnapshot()


def build_diagnostic_report(context: DiagnosticContext) -> str:
    """Return useful runtime metadata without project content or user paths."""

    values = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "locaforge_version": locaforge_version,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "pyside_version": pyside_version,
        "qt_version": qVersion(),
        "os": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "frozen_build": str(bool(getattr(sys, "frozen", False))).lower(),
        "ui_locale": context.ui_locale,
        "theme": context.theme,
        "online_lookup_enabled": str(context.online_lookup_enabled).lower(),
        "project_open": str(context.project_open).lower(),
        "project_format_version": _optional_value(context.project_format_version),
        "document_count": str(context.document_count),
        "entry_count": str(context.entry_count),
        "source_formats": ",".join(sorted(set(context.source_formats))) or "none",
        "project_dirty": str(context.project_dirty).lower(),
        "last_incident_id": get_last_incident_id() or "none",
        "model_request_count": str(context.model_performance.request_count),
        "model_total_seconds": _seconds(context.model_performance.total_duration_ns),
        "model_load_seconds": _seconds(context.model_performance.load_duration_ns),
        "model_prompt_tokens": str(context.model_performance.prompt_eval_count),
        "model_generated_tokens": str(context.model_performance.eval_count),
        "model_generation_tokens_per_second": (
            f"{context.model_performance.generation_tokens_per_second:.2f}"
        ),
    }
    lines = ["LocaForge diagnostic report"]
    lines.extend(f"{key}: {value}" for key, value in values.items())
    lines.extend(
        (
            "privacy: project names, paths, source strings, translations, prompts, and logs "
            "are not included",
            "end_of_report: true",
        )
    )
    return "\n".join(lines)


def _optional_value(value: object | None) -> str:
    return "unknown" if value is None else str(value)


def _seconds(nanoseconds: int) -> str:
    return f"{nanoseconds / 1_000_000_000:.3f}"
