from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from locaforge.domain.project_profile import ProjectProfile
from locaforge.domain.settings import ModelSettings
from locaforge.presentation.project_configuration_controller import (
    ProjectConfiguration,
    ProjectConfigurationController,
)


class WorkspaceStub:
    def __init__(
        self,
        *,
        has_project: bool = True,
        override_enabled: bool = False,
        model_settings: ModelSettings | None = None,
        models: tuple[str, ...] = ("model-a",),
        list_error: Exception | None = None,
    ) -> None:
        self.has_project = has_project
        self.models = models
        self.list_error = list_error
        self.project = SimpleNamespace(
            model_settings_override_enabled=override_enabled,
            model_settings=model_settings or ModelSettings(),
        )
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def list_models(self) -> tuple[str, ...]:
        if self.list_error is not None:
            raise self.list_error
        return self.models

    def update_model_settings(self, settings: ModelSettings) -> None:
        self.calls.append(("update_model_settings", (settings,)))

    def set_model_settings_override_enabled(self, enabled: bool) -> None:
        self.calls.append(("set_model_settings_override_enabled", (enabled,)))


class ProjectIoStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def __getattr__(self, name: str) -> Callable[..., bool]:
        def record(*args: object) -> bool:
            self.calls.append((name, args))
            return True

        return record


DEFAULT_CONFIGURATION = ProjectConfiguration(
    "LocaForge",
    "en",
    "ru",
    ProjectProfile(description="Desktop localization tool"),
)


def make_controller(
    workspace: WorkspaceStub,
    project_io: ProjectIoStub,
    *,
    confirm_unsaved: bool = True,
    new_configuration: ProjectConfiguration | None = DEFAULT_CONFIGURATION,
    destination: Path | None = Path("project.lfproj"),
    existing_configuration: ProjectConfiguration | None = DEFAULT_CONFIGURATION,
):
    new_requests: list[bool] = []
    destination_requests: list[str] = []
    existing_requests: list[tuple[str, ...]] = []
    messages: list[str] = []

    def ask_new() -> ProjectConfiguration | None:
        new_requests.append(True)
        return new_configuration

    def choose(name: str) -> Path | None:
        destination_requests.append(name)
        return destination

    def ask_existing(models) -> ProjectConfiguration | None:
        existing_requests.append(tuple(models))
        return existing_configuration

    def run_action(action, message: str) -> bool:
        action()
        messages.append(message)
        return True

    controller = ProjectConfigurationController(
        cast(Any, workspace),
        cast(Any, project_io),
        confirm_unsaved_changes=lambda: confirm_unsaved,
        ask_new_configuration=ask_new,
        choose_destination=choose,
        ask_existing_configuration=ask_existing,
        run_action=run_action,
    )
    return controller, new_requests, destination_requests, existing_requests, messages


def test_new_project_collects_configuration_and_delegates_creation() -> None:
    workspace = WorkspaceStub()
    project_io = ProjectIoStub()
    controller, new_requests, destinations, _, _ = make_controller(workspace, project_io)

    controller.new_project()

    assert new_requests == [True]
    assert destinations == ["LocaForge"]
    assert project_io.calls == [
        (
            "create_project",
            (
                Path("project.lfproj"),
                "LocaForge",
                "en",
                "ru",
                DEFAULT_CONFIGURATION.profile,
            ),
        )
    ]


def test_new_project_stops_before_dialog_or_creation_on_cancel() -> None:
    project_io = ProjectIoStub()
    declined, declined_requests, _, _, _ = make_controller(
        WorkspaceStub(), project_io, confirm_unsaved=False
    )
    no_configuration, _, no_config_destinations, _, _ = make_controller(
        WorkspaceStub(), project_io, new_configuration=None
    )
    no_destination, _, destination_requests, _, _ = make_controller(
        WorkspaceStub(), project_io, destination=None
    )

    declined.new_project()
    no_configuration.new_project()
    no_destination.new_project()

    assert declined_requests == []
    assert no_config_destinations == []
    assert destination_requests == ["LocaForge"]
    assert project_io.calls == []


def test_edit_updates_profile_and_enables_changed_override() -> None:
    settings = ModelSettings(model="special")
    configuration = ProjectConfiguration(
        "Updated", "de", "fr", ProjectProfile(tone="Formal"), True, settings
    )
    workspace = WorkspaceStub(override_enabled=False)
    project_io = ProjectIoStub()
    controller, _, _, model_requests, messages = make_controller(
        workspace, project_io, existing_configuration=configuration
    )

    controller.edit_project_settings()

    assert model_requests == [("model-a",)]
    assert project_io.calls == [
        (
            "update_project_profile",
            ("Updated", "de", "fr", configuration.profile),
        )
    ]
    assert workspace.calls == [("update_model_settings", (settings,))]
    assert messages == ["Project model settings updated"]


def test_edit_disables_existing_override() -> None:
    workspace = WorkspaceStub(override_enabled=True)
    project_io = ProjectIoStub()
    controller, _, _, _, messages = make_controller(workspace, project_io)

    controller.edit_project_settings()

    assert workspace.calls == [("set_model_settings_override_enabled", (False,))]
    assert messages == ["Model settings source updated"]


def test_unchanged_override_does_not_run_separate_model_action() -> None:
    settings = ModelSettings(model="special")
    configuration = ProjectConfiguration(
        "Updated", "en", "ru", ProjectProfile(), True, settings
    )
    workspace = WorkspaceStub(override_enabled=True, model_settings=settings)
    project_io = ProjectIoStub()
    controller, _, _, _, messages = make_controller(
        workspace, project_io, existing_configuration=configuration
    )

    controller.edit_project_settings()

    assert len(project_io.calls) == 1
    assert workspace.calls == []
    assert messages == []


def test_edit_handles_unavailable_model_list_and_cancelled_dialog() -> None:
    workspace = WorkspaceStub(list_error=ConnectionError("offline"))
    project_io = ProjectIoStub()
    controller, _, _, model_requests, _ = make_controller(
        workspace, project_io, existing_configuration=None
    )

    controller.edit_project_settings()

    assert model_requests == [()]
    assert project_io.calls == []


def test_edit_requires_open_project() -> None:
    workspace = WorkspaceStub(has_project=False)
    project_io = ProjectIoStub()
    controller, _, _, model_requests, _ = make_controller(workspace, project_io)

    controller.edit_project_settings()

    assert model_requests == []
    assert project_io.calls == []
