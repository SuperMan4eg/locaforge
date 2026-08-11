"""New-project and project-settings orchestration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.project_profile import ProjectProfile
from locaforge.domain.settings import ModelSettings
from locaforge.presentation.project_io_controller import ProjectIoController

type ProjectAction = Callable[[], object]
type ActionRunner = Callable[[ProjectAction, str], bool]


@dataclass(frozen=True, slots=True)
class ProjectConfiguration:
    name: str
    source_language: str
    target_language: str
    profile: ProjectProfile
    model_settings_override_enabled: bool = False
    model_settings: ModelSettings = ModelSettings()


class ProjectConfigurationController:
    """Coordinates project creation and updates to project-level settings."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        project_io: ProjectIoController,
        confirm_unsaved_changes: Callable[[], bool],
        ask_new_configuration: Callable[[], ProjectConfiguration | None],
        choose_destination: Callable[[str], Path | None],
        ask_existing_configuration: Callable[
            [Sequence[str]], ProjectConfiguration | None
        ],
        run_action: ActionRunner,
    ) -> None:
        self._workspace = workspace
        self._project_io = project_io
        self._confirm_unsaved_changes = confirm_unsaved_changes
        self._ask_new_configuration = ask_new_configuration
        self._choose_destination = choose_destination
        self._ask_existing_configuration = ask_existing_configuration
        self._run_action = run_action

    def new_project(self) -> None:
        if not self._confirm_unsaved_changes():
            return
        configuration = self._ask_new_configuration()
        if configuration is None:
            return
        destination = self._choose_destination(configuration.name)
        if destination is None:
            return
        self._project_io.create_project(
            destination,
            configuration.name,
            configuration.source_language,
            configuration.target_language,
            configuration.profile,
        )

    def edit_project_settings(self) -> None:
        if not self._workspace.has_project:
            return
        try:
            available_models = self._workspace.list_models()
        except Exception:
            available_models = ()
        configuration = self._ask_existing_configuration(available_models)
        if configuration is None:
            return
        self._project_io.update_project_profile(
            configuration.name,
            configuration.source_language,
            configuration.target_language,
            configuration.profile,
        )
        project = self._workspace.project
        if configuration.model_settings_override_enabled and (
            not project.model_settings_override_enabled
            or configuration.model_settings != project.model_settings
        ):
            self._run_action(
                lambda: self._workspace.update_model_settings(configuration.model_settings),
                "Project model settings updated",
            )
        elif (
            not configuration.model_settings_override_enabled
            and project.model_settings_override_enabled
        ):
            self._run_action(
                lambda: self._workspace.set_model_settings_override_enabled(False),
                "Model settings source updated",
            )
