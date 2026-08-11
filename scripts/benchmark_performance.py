"""Reproducible performance baseline for representative LocaForge workflows."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.request import Request, urlopen

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if TYPE_CHECKING:
    from locaforge.application.project_session import ProjectSession
    from locaforge.domain.project import Project
    from locaforge.infrastructure.persistence.lfproj_container import LfprojContainer
    from locaforge.infrastructure.persistence.sqlite_project_repository import (
        SQLiteProjectRepository,
    )
    from locaforge.presentation.translation_filter_proxy import TranslationFilterProxyModel
    from locaforge.presentation.translation_table_model import TranslationTableModel

_SCHEMA_VERSION = 1
_DEFAULT_SIZES = (1_000, 10_000, 50_000)


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Timing distribution for one scenario and data size."""

    scenario: str
    size: int
    iterations: int
    median_ms: float
    p95_ms: float
    minimum_ms: float
    maximum_ms: float
    samples_ms: tuple[float, ...]
    details: dict[str, float | int | str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """Machine-readable result envelope used for before/after comparisons."""

    schema_version: int
    generated_at: str
    environment: dict[str, str]
    configuration: dict[str, object]
    results: tuple[BenchmarkResult, ...]


@dataclass(slots=True)
class ProjectFixture:
    """Isolated persistent project and UI models used by benchmark scenarios."""

    project: Project
    repository: SQLiteProjectRepository
    container: LfprojContainer
    session: ProjectSession
    project_path: Path
    table_model: TranslationTableModel
    proxy_model: TranslationFilterProxyModel


def _percentile(samples: Sequence[float], percentile: float) -> float:
    if not samples:
        raise ValueError("Cannot calculate a percentile without samples")
    ordered = sorted(samples)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def summarize(
    scenario: str,
    size: int,
    samples_ms: Sequence[float],
    details: dict[str, float | int | str] | None = None,
) -> BenchmarkResult:
    """Build stable summary statistics without interpolating short sample sets."""
    if not samples_ms:
        raise ValueError("A benchmark result requires at least one sample")
    samples = tuple(round(value, 6) for value in samples_ms)
    return BenchmarkResult(
        scenario=scenario,
        size=size,
        iterations=len(samples),
        median_ms=round(statistics.median(samples), 6),
        p95_ms=round(_percentile(samples, 0.95), 6),
        minimum_ms=round(min(samples), 6),
        maximum_ms=round(max(samples), 6),
        samples_ms=samples,
        details=dict(details or {}),
    )


def measure(
    scenario: str,
    size: int,
    action: Callable[[], object],
    *,
    warmups: int,
    iterations: int,
    details: dict[str, float | int | str] | None = None,
) -> BenchmarkResult:
    """Warm up and measure one action using a monotonic high-resolution clock."""
    for _ in range(warmups):
        action()
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        action()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return summarize(scenario, size, samples, details)


def runtime_metadata() -> dict[str, str]:
    """Describe optional interpreter modes without dropping Python 3.12 support."""
    jit = getattr(sys, "_jit", None)
    jit_available = getattr(jit, "is_available", None)
    jit_enabled = getattr(jit, "is_enabled", None)
    gil_enabled = getattr(sys, "_is_gil_enabled", None)
    return {
        "python_jit_available": str(jit_available() if callable(jit_available) else False),
        "python_jit_enabled": str(jit_enabled() if callable(jit_enabled) else False),
        "python_gil_enabled": str(gil_enabled() if callable(gil_enabled) else True),
        "python_compiled": str("__compiled__" in globals()),
    }


def _make_project(size: int, document_count: int) -> Project:
    from locaforge.domain.document import ProjectDocument
    from locaforge.domain.entry import EntryStatus, TranslationEntry
    from locaforge.domain.project import Project

    documents = [
        ProjectDocument(
            id=f"document-{index}",
            name=f"file-{index}.json",
            source_path=f"folder-{index % 20}/file-{index}.json",
            source_format="json",
            source_document={},
        )
        for index in range(document_count)
    ]
    entries = []
    for index in range(size):
        translated = index % 5 != 0
        entries.append(
            TranslationEntry(
                id=f"entry-{index}",
                key_path=("messages", index),
                source=f"Synthetic source string {index}" + (" needle" if index % 997 == 0 else ""),
                translation=f"Synthetic translation {index}" if translated else None,
                status=EntryStatus.NEEDS_REVIEW if translated else EntryStatus.UNTRANSLATED,
                context=f"screen-{index % 50}",
                document_id=documents[index % document_count].id,
            )
        )
    return Project(
        id=f"benchmark-{size}",
        name=f"Benchmark {size}",
        source_language="en",
        target_language="ru",
        entries=entries,
        documents=documents,
        dirty=True,
    )


def _make_fixture(root: Path, size: int, document_count: int) -> ProjectFixture:
    from locaforge.infrastructure.persistence.lfproj_container import LfprojContainer
    from locaforge.infrastructure.persistence.sqlite_project_repository import (
        SQLiteProjectRepository,
    )
    from locaforge.presentation.translation_filter_proxy import TranslationFilterProxyModel
    from locaforge.presentation.translation_table_model import TranslationTableModel

    fixture_root = root / f"fixture-{size}"
    container = LfprojContainer(fixture_root / "workspaces")
    project = _make_project(size, document_count)
    session = container.create(
        {"project_id": project.id, "source_format": "json", "source_file": "fixture.json"}
    )
    repository = SQLiteProjectRepository(session.database_path)
    repository.create(project)
    project_path = fixture_root / f"benchmark-{size}.lfproj"
    container.save(session, project_path)

    table_model = TranslationTableModel()
    table_model.set_entries(project.entries)
    proxy_model = TranslationFilterProxyModel()
    proxy_model.setSourceModel(table_model)
    return ProjectFixture(
        project,
        repository,
        container,
        session,
        project_path,
        table_model,
        proxy_model,
    )


def _project_cases(
    fixture: ProjectFixture,
    *,
    warmups: int,
    iterations: int,
) -> list[BenchmarkResult]:
    from PySide6.QtWidgets import QListWidget, QTreeWidget

    from locaforge.application.services.project_persistence import ProjectPersistenceService
    from locaforge.application.services.project_reporting import ProjectReportingService
    from locaforge.application.services.project_validation import ProjectValidationService
    from locaforge.application.services.translation_editing import TranslationEditingService
    from locaforge.application.use_cases.save_project_file import SaveProjectFile
    from locaforge.domain.entry import EntryStatus, TranslationEntry
    from locaforge.infrastructure.persistence.sqlite_project_repository_factory import (
        SQLiteProjectRepositoryFactory,
    )
    from locaforge.presentation.project_explorer_controller import ProjectExplorerController

    project = fixture.project
    size = len(project.entries)
    lookup_ids = tuple(
        f"entry-{round(index * (size - 1) / max(1, min(size, 1_000) - 1))}"
        for index in range(min(size, 1_000))
    )
    reporting = ProjectReportingService()
    factory = SQLiteProjectRepositoryFactory()
    persistence = ProjectPersistenceService(fixture.container, factory)
    editing = TranslationEditingService(None, None)
    explorer_list = QListWidget()
    explorer_tree = QTreeWidget()

    class ExplorerWorkspace:
        has_project = True

        def __init__(self, benchmark_project: Project) -> None:
            self.project = benchmark_project

        def project_statistics(self) -> object:
            return reporting.statistics(self.project, ())

    explorer = ProjectExplorerController(
        ExplorerWorkspace(project),  # type: ignore[arg-type]
        explorer_list,
        file_tree=explorer_tree,
    )
    search_state = iter(("needle", "not-present") * (warmups + iterations + 1))
    document_state = iter(
        ("document-0", f"document-{max(0, len(project.documents) - 1)}")
        * (warmups + iterations + 1)
    )

    def search_table() -> int:
        fixture.proxy_model.set_search_text(next(search_state))
        return fixture.proxy_model.rowCount()

    def switch_document() -> int:
        fixture.proxy_model.set_document_id(next(document_state))
        return fixture.proxy_model.rowCount()

    def open_container() -> int:
        session = fixture.container.open(fixture.project_path)
        return factory.create(session.database_path).get(project.id).entries.__len__()

    update_state = 0

    def update_last_table_entry() -> None:
        nonlocal update_state
        update_state += 1
        original = project.entries[-1]
        fixture.table_model.update_entry(
            TranslationEntry(
                id=original.id,
                key_path=original.key_path,
                source=original.source,
                translation=f"Updated {update_state}",
                status=EntryStatus.NEEDS_REVIEW,
                context=original.context,
                document_id=original.document_id,
            )
        )

    edit_state = 0

    def edit_translation() -> None:
        nonlocal edit_state
        edit_state += 1
        editing.edit(
            fixture.repository,
            project,
            project.entries[-1].id,
            f"Benchmark edit {edit_state}",
        )

    def undo_redo_cycle() -> None:
        fixture.repository.undo_last_translation_operation(project.id)
        fixture.repository.redo_last_translation_operation(project.id)

    results = [
        measure(
            "project_entry_lookup_1000",
            size,
            lambda: tuple(project.get_entry(entry_id) for entry_id in lookup_ids),
            warmups=warmups,
            iterations=iterations,
            details={"lookups": len(lookup_ids)},
        ),
        measure(
            "project_statistics",
            size,
            lambda: reporting.statistics(project, ()),
            warmups=warmups,
            iterations=iterations,
        ),
        measure(
            "table_text_filter",
            size,
            search_table,
            warmups=warmups,
            iterations=iterations,
        ),
        measure(
            "table_document_filter",
            size,
            switch_document,
            warmups=warmups,
            iterations=iterations,
            details={"documents": len(project.documents)},
        ),
        measure(
            "table_update_last_entry",
            size,
            update_last_table_entry,
            warmups=warmups,
            iterations=iterations,
        ),
        measure(
            "project_explorer_refresh",
            size,
            explorer.refresh,
            warmups=warmups,
            iterations=iterations,
            details={"documents": len(project.documents)},
        ),
        measure(
            "open_lfproj",
            size,
            open_container,
            warmups=warmups,
            iterations=iterations,
        ),
        measure(
            "edit_translation",
            size,
            edit_translation,
            warmups=warmups,
            iterations=iterations,
        ),
        measure(
            "undo_redo_cycle",
            size,
            undo_redo_cycle,
            warmups=warmups,
            iterations=iterations,
        ),
        measure(
            "validate_project",
            size,
            lambda: ProjectValidationService(None).validate(fixture.repository, project),
            warmups=warmups,
            iterations=iterations,
        ),
        measure(
            "repository_full_save",
            size,
            lambda: fixture.repository.save(project),
            warmups=warmups,
            iterations=iterations,
        ),
        measure(
            "manual_save_lfproj",
            size,
            lambda: SaveProjectFile(fixture.container, factory).execute(fixture.session),
            warmups=warmups,
            iterations=iterations,
        ),
        measure(
            "autosave_lfproj",
            size,
            lambda: persistence.autosave(
                fixture.repository,
                fixture.session,
                project,
            ),
            warmups=warmups,
            iterations=iterations,
        ),
    ]
    return results


def _translation_memory_result(
    root: Path, *, warmups: int, iterations: int, record_count: int
) -> BenchmarkResult:
    from locaforge.domain.translation_memory import TranslationMemoryRecord
    from locaforge.infrastructure.persistence.sqlite_translation_memory import (
        SQLiteTranslationMemory,
    )

    database_path = root / "translation-memory.db"
    store = SQLiteTranslationMemory(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.executemany(
            "INSERT INTO translation_memory "
            "(source_language, target_language, source, context, translation, source_length) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    "en",
                    "ru",
                    f"Synthetic memory source {index}",
                    "",
                    f"Translation {index}",
                    len(f"Synthetic memory source {index}"),
                )
                for index in range(record_count)
            ],
        )
        connection.commit()
    query = TranslationMemoryRecord("en", "ru", "Synthetic memory source 4242", "Translation", "")
    return measure(
        "translation_memory_similar",
        record_count,
        lambda: store.find_similar(
            query.source_language,
            query.target_language,
            query.source,
            query.context,
        ),
        warmups=warmups,
        iterations=iterations,
        details={"candidate_limit": 300, "scorer": "rapidfuzz.ratio"},
    )


def _glossary_result(
    root: Path,
    *,
    warmups: int,
    iterations: int,
    source_count: int,
    term_count: int,
) -> BenchmarkResult:
    from locaforge.infrastructure.persistence.sqlite_glossary import SQLiteGlossary

    database_path = root / "glossary.db"
    store = SQLiteGlossary(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.executemany(
            "INSERT INTO glossary "
            "(source_language, target_language, source, target, case_sensitive) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                ("en", "ru", f"term{index}", f"translation{index}", 0)
                for index in range(term_count)
            ],
        )
        connection.commit()
    sources = tuple(
        f"Synthetic source containing term{index % term_count} value"
        for index in range(source_count)
    )
    return measure(
        "glossary_batch_match",
        source_count,
        lambda: store.find_for_sources_batch("en", "ru", sources),
        warmups=warmups,
        iterations=iterations,
        details={"terms": term_count},
    )


def _startup_result(root: Path, *, warmups: int, iterations: int) -> BenchmarkResult:
    command = [sys.executable, str(Path(__file__).resolve()), "--startup-child", str(root)]
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"

    def start_application() -> None:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            env=environment,
            timeout=60,
        )

    return measure(
        "cold_ui_startup",
        0,
        start_application,
        warmups=warmups,
        iterations=iterations,
    )


def _ollama_result(
    base_url: str,
    model: str,
    *,
    entry_count: int,
    keep_alive_seconds: int,
    warmups: int,
    iterations: int,
) -> BenchmarkResult:
    entries = [
        {"entry_id": f"entry-{index}", "source": f"Synthetic source {index}"}
        for index in range(entry_count)
    ]
    prompt = json.dumps(
        entries
    )
    payload = json.dumps(
        {
            "model": model,
            "prompt": (
                "Translate every item to Russian. Return only a JSON object in the form "
                '{"translations":[{"entry_id":"entry-0","translation":"..."}]}. '
                "Preserve every entry_id and return exactly one result per input item. Input: "
                + prompt
            ),
            "stream": False,
            "format": "json",
            "think": False,
            "keep_alive": keep_alive_seconds,
        }
    ).encode("utf-8")
    responses: list[dict[str, Any]] = []

    def generate() -> None:
        request = Request(
            f"{base_url.rstrip('/')}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=600) as response:  # noqa: S310
            body = json.loads(response.read().decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("Ollama benchmark received a non-object response")
        responses.append(body)

    result = measure(
        "ollama_generate_batch",
        entry_count,
        generate,
        warmups=warmups,
        iterations=iterations,
        details={"model": model, "keep_alive_seconds": keep_alive_seconds},
    )
    measured_responses = responses[-iterations:]
    metric_names = (
        "total_duration",
        "load_duration",
        "prompt_eval_count",
        "prompt_eval_duration",
        "eval_count",
        "eval_duration",
    )
    details = dict(result.details)
    for name in metric_names:
        values = [
            response[name] for response in measured_responses if isinstance(response.get(name), int)
        ]
        if values:
            details[f"median_{name}"] = round(statistics.median(values), 3)
    total_durations = [
        int(response["total_duration"])
        for response in measured_responses
        if isinstance(response.get("total_duration"), int)
        and not isinstance(response.get("total_duration"), bool)
        and int(response["total_duration"]) > 0
    ]
    if total_durations:
        median_total_seconds = statistics.median(total_durations) / 1_000_000_000
        details["offered_entries_per_minute"] = round(
            entry_count * 60 / median_total_seconds, 3
        )
        valid_counts = [_valid_translation_count(response) for response in measured_responses]
        median_valid_count = statistics.median(valid_counts)
        details["median_returned_entries"] = round(median_valid_count, 3)
        details["completion_percent"] = round(median_valid_count * 100 / entry_count, 3)
        details["returned_entries_per_minute"] = round(
            median_valid_count * 60 / median_total_seconds, 3
        )
    eval_counts = [
        int(response["eval_count"])
        for response in measured_responses
        if isinstance(response.get("eval_count"), int)
        and not isinstance(response.get("eval_count"), bool)
    ]
    eval_durations = [
        int(response["eval_duration"])
        for response in measured_responses
        if isinstance(response.get("eval_duration"), int)
        and not isinstance(response.get("eval_duration"), bool)
    ]
    total_eval_count = sum(eval_counts)
    total_eval_duration = sum(eval_durations)
    if total_eval_duration > 0:
        details["generation_tokens_per_second"] = round(
            total_eval_count * 1_000_000_000 / total_eval_duration, 3
        )
    return BenchmarkResult(**{**asdict(result), "details": details})


def _valid_translation_count(response: dict[str, Any]) -> int:
    raw_response = response.get("response")
    if not isinstance(raw_response, str):
        return 0
    try:
        body = json.loads(raw_response)
    except json.JSONDecodeError:
        return 0
    translations = body.get("translations") if isinstance(body, dict) else None
    if not isinstance(translations, list):
        return 0
    result_ids = {
        item["entry_id"]
        for item in translations
        if isinstance(item, dict)
        and isinstance(item.get("entry_id"), str)
        and isinstance(item.get("translation"), str)
    }
    return len(result_ids)


def run_benchmarks(
    root: Path,
    *,
    sizes: Sequence[int],
    iterations: int,
    warmups: int,
    document_count: int,
    include_startup: bool,
    translation_memory_records: int,
    glossary_sources: int,
    glossary_terms: int,
    ollama_url: str | None = None,
    ollama_model: str | None = None,
    ollama_batch_sizes: Sequence[int] = (5, 10, 20, 40),
    ollama_keep_alive_seconds: int = 300,
) -> BenchmarkReport:
    """Run all configured scenarios inside an isolated temporary root."""
    from PySide6 import __version__ as pyside_version
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()
    if not isinstance(application, QApplication):
        application = QApplication([])
    results: list[BenchmarkResult] = []
    if include_startup:
        results.append(_startup_result(root / "startup", warmups=warmups, iterations=iterations))
    for size in sizes:
        documents = min(document_count, max(1, size))
        fixture = _make_fixture(root, size, documents)
        results.extend(_project_cases(fixture, warmups=warmups, iterations=iterations))
    results.append(
        _translation_memory_result(
            root,
            warmups=warmups,
            iterations=iterations,
            record_count=translation_memory_records,
        )
    )
    results.append(
        _glossary_result(
            root,
            warmups=warmups,
            iterations=iterations,
            source_count=glossary_sources,
            term_count=glossary_terms,
        )
    )
    if ollama_url and ollama_model:
        results.extend(
            _ollama_result(
                ollama_url,
                ollama_model,
                entry_count=batch_size,
                keep_alive_seconds=ollama_keep_alive_seconds,
                warmups=warmups,
                iterations=iterations,
            )
            for batch_size in ollama_batch_sizes
        )
    if application is None:  # pragma: no cover - QApplication construction is guaranteed
        raise RuntimeError("Qt application could not be created")
    return BenchmarkReport(
        schema_version=_SCHEMA_VERSION,
        generated_at=datetime.now(UTC).isoformat(),
        environment={
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            **runtime_metadata(),
            "pyside": pyside_version,
            "platform": platform.platform(),
            "processor": platform.processor() or "unknown",
            "sqlite": sqlite3.sqlite_version,
        },
        configuration={
            "sizes": list(sizes),
            "iterations": iterations,
            "warmups": warmups,
            "documents": document_count,
            "translation_memory_records": translation_memory_records,
            "glossary_sources": glossary_sources,
            "glossary_terms": glossary_terms,
            "startup_included": include_startup,
            "ollama_included": bool(ollama_url and ollama_model),
            "ollama_batch_sizes": list(ollama_batch_sizes),
            "ollama_keep_alive_seconds": ollama_keep_alive_seconds,
        },
        results=tuple(results),
    )


def render_markdown(report: BenchmarkReport) -> str:
    """Render a compact human-readable report alongside canonical JSON output."""
    lines = [
        "# LocaForge performance baseline",
        "",
        f"Generated: `{report.generated_at}`",
        "",
        "| Scenario | Size | Median, ms | p95, ms | Min, ms | Max, ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in report.results:
        lines.append(
            f"| `{result.scenario}` | {result.size} | {result.median_ms:.3f} | "
            f"{result.p95_ms:.3f} | {result.minimum_ms:.3f} | {result.maximum_ms:.3f} |"
        )
    lines.extend(("", "## Environment", ""))
    lines.extend(f"- {key}: `{value}`" for key, value in report.environment.items())
    return "\n".join(lines) + "\n"


def _write_report(
    report: BenchmarkReport, json_path: Path | None, markdown_path: Path | None
) -> None:
    payload = asdict(report)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if json_path is None:
        print(encoded, end="")
    else:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(encoded, encoding="utf-8")
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report), encoding="utf-8")


def _run_startup_child(data_root: Path) -> int:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from locaforge.app.bootstrap import build_workspace
    from locaforge.presentation.localization import LocalizationManager
    from locaforge.presentation.main_window import MainWindow

    application = QApplication.instance()
    if not isinstance(application, QApplication):
        application = QApplication([])
    application.setApplicationName("LocaForge Benchmark")
    application.setOrganizationName("LocaForge Benchmark")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(data_root))
    localization = LocalizationManager(data_root / "localizations", "en")
    localization.install(application)
    window = MainWindow(
        build_workspace(data_root),
        application_settings=None,
        localization=localization,
    )
    window.show()
    application.processEvents()
    window.close()
    application.processEvents()
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=list(_DEFAULT_SIZES))
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--documents", type=int, default=500)
    parser.add_argument("--translation-memory-records", type=int, default=10_000)
    parser.add_argument("--glossary-sources", type=int, default=500)
    parser.add_argument("--glossary-terms", type=int, default=200)
    parser.add_argument("--skip-startup", action="store_true")
    parser.add_argument("--ollama-url")
    parser.add_argument("--ollama-model")
    parser.add_argument("--ollama-batch-sizes", nargs="+", type=int, default=[5, 10, 20, 40])
    parser.add_argument("--ollama-keep-alive-seconds", type=int, default=300)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--startup-child", type=Path, help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.startup_child is not None:
        return _run_startup_child(args.startup_child)
    if args.iterations < 1 or args.warmups < 0:
        raise SystemExit("iterations must be positive and warmups cannot be negative")
    if any(size < 1 for size in args.sizes):
        raise SystemExit("all project sizes must be positive")
    if args.glossary_sources < 1 or args.glossary_terms < 1:
        raise SystemExit("glossary source and term counts must be positive")
    if bool(args.ollama_url) != bool(args.ollama_model):
        raise SystemExit("--ollama-url and --ollama-model must be supplied together")
    if any(size < 1 for size in args.ollama_batch_sizes):
        raise SystemExit("all Ollama batch sizes must be positive")
    if args.ollama_keep_alive_seconds < -1:
        raise SystemExit("Ollama keep-alive must be -1 or a non-negative number of seconds")
    if args.quick:
        args.sizes = [100]
        args.iterations = 1
        args.warmups = 0
        args.documents = 10
        args.translation_memory_records = 100
        args.glossary_sources = 50
        args.glossary_terms = 20
    with tempfile.TemporaryDirectory(prefix="locaforge-benchmark-") as temporary_directory:
        report = run_benchmarks(
            Path(temporary_directory),
            sizes=args.sizes,
            iterations=args.iterations,
            warmups=args.warmups,
            document_count=args.documents,
            include_startup=not args.skip_startup,
            translation_memory_records=args.translation_memory_records,
            glossary_sources=args.glossary_sources,
            glossary_terms=args.glossary_terms,
            ollama_url=args.ollama_url,
            ollama_model=args.ollama_model,
            ollama_batch_sizes=args.ollama_batch_sizes,
            ollama_keep_alive_seconds=args.ollama_keep_alive_seconds,
        )
    _write_report(report, args.json, args.markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
