import tomllib
from pathlib import Path

from locaforge import __version__
from locaforge.app import exception_handler
from locaforge.app.diagnostics import DiagnosticContext, build_diagnostic_report


def test_runtime_version_matches_project_metadata() -> None:
    project_root = Path(__file__).resolve().parents[3]
    metadata = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == metadata["project"]["version"]


def test_diagnostic_report_contains_only_safe_runtime_and_project_metadata() -> None:
    report = build_diagnostic_report(
        DiagnosticContext(
            ui_locale="ru",
            theme="dark",
            online_lookup_enabled=False,
            project_open=True,
            project_format_version=2,
            document_count=4,
            entry_count=120,
            source_formats=("xml", "json", "json"),
            project_dirty=True,
        )
    )

    assert "project_format_version: 2" in report
    assert "document_count: 4" in report
    assert "entry_count: 120" in report
    assert "source_formats: json,xml" in report
    assert "project_dirty: true" in report
    assert "end_of_report: true" in report
    assert "project_name" not in report
    assert "source_string" not in report
    assert "translation:" not in report


def test_diagnostic_report_handles_absent_project() -> None:
    report = build_diagnostic_report(
        DiagnosticContext("en", "system", online_lookup_enabled=False)
    )

    assert "project_open: false" in report
    assert "project_format_version: unknown" in report
    assert "source_formats: none" in report


def test_diagnostic_report_links_last_incident_without_exception_details() -> None:
    exception_handler._record_incident("A1B2C3D4")

    report = build_diagnostic_report(
        DiagnosticContext("en", "system", online_lookup_enabled=False)
    )

    assert "last_incident_id: A1B2C3D4" in report
