from types import SimpleNamespace
from typing import Any, cast

from locaforge.presentation.application_settings import ApplicationSettings
from locaforge.presentation.project_information_controller import (
    ProjectInformationController,
)


class WorkspaceStub:
    def __init__(
        self,
        *,
        has_project: bool = True,
        format_version: object = 3,
    ) -> None:
        self.has_project = has_project
        self.project = SimpleNamespace(
            documents=(
                SimpleNamespace(source_format="json"),
                SimpleNamespace(source_format="po"),
            ),
            entries=(object(), object(), object()),
            dirty=True,
        )
        self.session = SimpleNamespace(metadata={"format_version": format_version})


def make_controller(
    workspace: WorkspaceStub,
    *,
    context: str = "Project context",
    copy_succeeds: bool = True,
):
    information: list[tuple[str, str]] = []
    copied: list[str] = []
    notifications: list[bool] = []

    def copy_text(text: str) -> bool:
        copied.append(text)
        return copy_succeeds

    controller = ProjectInformationController(
        cast(Any, workspace),
        application_settings=lambda: ApplicationSettings(
            ui_locale="ru-RU",
            theme="dark",
            allow_online_project_lookup=True,
        ),
        show_information=lambda title, message: information.append((title, message)),
        copy_text=copy_text,
        diagnostics_copied=lambda: notifications.append(True),
        build_project_context=lambda _project: context,
    )
    return controller, information, copied, notifications


def test_context_preview_requires_project_and_shows_built_context() -> None:
    controller, information, _, _ = make_controller(WorkspaceStub())
    missing, missing_information, _, _ = make_controller(
        WorkspaceStub(has_project=False)
    )

    controller.preview_project_context()
    missing.preview_project_context()

    assert information == [("AI project context", "Project context")]
    assert missing_information == []


def test_empty_context_uses_settings_hint() -> None:
    controller, information, _, _ = make_controller(WorkspaceStub(), context="")

    controller.preview_project_context()

    assert information == [
        (
            "AI project context",
            "No project context is configured yet. Open Project settings to add it.",
        )
    ]


def test_diagnostics_include_safe_project_and_application_metadata() -> None:
    controller, _, copied, notifications = make_controller(WorkspaceStub())

    controller.copy_diagnostics()

    report = copied[0]
    assert "ui_locale: ru-RU" in report
    assert "theme: dark" in report
    assert "online_lookup_enabled: true" in report
    assert "project_open: true" in report
    assert "project_format_version: 3" in report
    assert "document_count: 2" in report
    assert "entry_count: 3" in report
    assert "source_formats: json,po" in report
    assert "project_dirty: true" in report
    assert notifications == [True]


def test_diagnostics_without_project_use_empty_safe_defaults() -> None:
    controller, _, copied, _ = make_controller(WorkspaceStub(has_project=False))

    controller.copy_diagnostics()

    report = copied[0]
    assert "project_open: false" in report
    assert "project_format_version: unknown" in report
    assert "document_count: 0" in report
    assert "entry_count: 0" in report
    assert "source_formats: none" in report
    assert "project_dirty: false" in report


def test_boolean_format_version_is_not_reported_as_integer() -> None:
    controller, _, copied, _ = make_controller(WorkspaceStub(format_version=True))

    controller.copy_diagnostics()

    assert "project_format_version: unknown" in copied[0]


def test_failed_clipboard_copy_does_not_show_success_notification() -> None:
    controller, _, copied, notifications = make_controller(
        WorkspaceStub(), copy_succeeds=False
    )

    controller.copy_diagnostics()

    assert len(copied) == 1
    assert notifications == []
