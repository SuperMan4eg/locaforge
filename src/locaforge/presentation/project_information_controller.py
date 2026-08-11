"""Read-only project context and diagnostic reporting orchestration."""

from __future__ import annotations

from collections.abc import Callable

from locaforge.app.diagnostics import DiagnosticContext, build_diagnostic_report
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.application.services.project_context_builder import ProjectContextBuilder
from locaforge.domain.project import Project
from locaforge.presentation.application_settings import ApplicationSettings


class ProjectInformationController:
    """Builds user-visible project context and privacy-safe diagnostics."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        application_settings: Callable[[], ApplicationSettings],
        show_information: Callable[[str, str], None],
        copy_text: Callable[[str], bool],
        diagnostics_copied: Callable[[], None],
        build_project_context: Callable[[Project], str] | None = None,
    ) -> None:
        self._workspace = workspace
        self._application_settings = application_settings
        self._show_information = show_information
        self._copy_text = copy_text
        self._diagnostics_copied = diagnostics_copied
        self._build_project_context = build_project_context or ProjectContextBuilder().build

    def preview_project_context(self) -> None:
        if not self._workspace.has_project:
            return
        context = self._build_project_context(self._workspace.project)
        self._show_information(
            "AI project context",
            context
            or "No project context is configured yet. Open Project settings to add it.",
        )

    def copy_diagnostics(self) -> None:
        project = self._workspace.project if self._workspace.has_project else None
        raw_format_version = (
            self._workspace.session.metadata.get("format_version")
            if self._workspace.has_project
            else None
        )
        format_version = (
            raw_format_version
            if isinstance(raw_format_version, int)
            and not isinstance(raw_format_version, bool)
            else None
        )
        settings = self._application_settings()
        report = build_diagnostic_report(
            DiagnosticContext(
                ui_locale=settings.ui_locale,
                theme=settings.theme,
                online_lookup_enabled=settings.allow_online_project_lookup,
                project_open=project is not None,
                project_format_version=format_version,
                document_count=len(project.documents) if project is not None else 0,
                entry_count=len(project.entries) if project is not None else 0,
                source_formats=(
                    tuple(document.source_format for document in project.documents)
                    if project is not None
                    else ()
                ),
                project_dirty=project.dirty if project is not None else False,
                model_performance=self._workspace.model_performance_snapshot(),
            )
        )
        if self._copy_text(report):
            self._diagnostics_copied()
