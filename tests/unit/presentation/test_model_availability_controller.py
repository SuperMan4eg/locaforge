from typing import Any, cast

from locaforge.domain.settings import ModelSettings
from locaforge.presentation.model_availability_controller import (
    ModelAvailabilityController,
)


class WorkspaceStub:
    def __init__(
        self,
        *,
        models: tuple[str, ...] = (),
        list_error: Exception | None = None,
        settings: ModelSettings | None = None,
    ) -> None:
        self.models = models
        self.list_error = list_error
        self.settings = settings or ModelSettings(model="configured", review_model="reviewer")
        self.updated: list[ModelSettings] = []

    def list_models(self) -> tuple[str, ...]:
        if self.list_error is not None:
            raise self.list_error
        return self.models

    def resolve_model_settings(self) -> ModelSettings:
        return self.settings

    def update_model_settings(self, settings: ModelSettings) -> None:
        self.updated.append(settings)


def make_controller(
    workspace: WorkspaceStub,
    *,
    selected: str | None = None,
    confirm_download: bool = False,
):
    choices: list[tuple[str, tuple[str, ...]]] = []
    downloads: list[str] = []
    installation_offers: list[bool] = []
    pulls: list[str] = []
    displayed: list[str] = []

    def choose(configured: str, installed) -> str | None:
        choices.append((configured, tuple(installed)))
        return selected

    def confirm(model: str) -> bool:
        downloads.append(model)
        return confirm_download

    controller = ModelAvailabilityController(
        cast(Any, workspace),
        choose_model=choose,
        confirm_download=confirm,
        offer_ollama_installation=lambda: installation_offers.append(True),
        start_model_pull=lambda model: pulls.append(model),
        set_displayed_model=displayed.append,
    )
    return controller, choices, downloads, installation_offers, pulls, displayed


def test_installed_model_is_immediately_available() -> None:
    workspace = WorkspaceStub(models=("configured", "other"))
    controller, choices, downloads, offers, pulls, displayed = make_controller(workspace)

    assert controller.ensure_available("configured") is True

    assert choices == downloads == offers == pulls == displayed == []
    assert workspace.updated == []


def test_unavailable_ollama_offers_installation() -> None:
    workspace = WorkspaceStub(list_error=ConnectionError("offline"))
    controller, choices, downloads, offers, pulls, _ = make_controller(workspace)

    assert controller.ensure_available("configured") is False

    assert offers == [True]
    assert choices == downloads == pulls == []


def test_selecting_installed_translation_model_updates_settings_and_display() -> None:
    workspace = WorkspaceStub(models=("available",))
    controller, choices, downloads, _, pulls, displayed = make_controller(
        workspace, selected="available"
    )

    assert controller.ensure_available("configured") is True

    assert choices == [("configured", ("available",))]
    assert downloads == pulls == []
    assert workspace.updated == [
        ModelSettings(model="available", review_model="reviewer")
    ]
    assert displayed == ["available"]


def test_selecting_review_model_updates_only_reviewer_setting() -> None:
    workspace = WorkspaceStub(models=("available-reviewer",))
    controller, _, _, _, _, displayed = make_controller(
        workspace, selected="available-reviewer"
    )

    assert controller.ensure_available("missing-reviewer", reviewer=True) is True

    assert workspace.updated == [
        ModelSettings(model="configured", review_model="available-reviewer")
    ]
    assert displayed == ["configured"]


def test_cancelled_selection_does_not_offer_download() -> None:
    workspace = WorkspaceStub(models=("available",))
    controller, choices, downloads, _, pulls, _ = make_controller(workspace, selected=None)

    assert controller.ensure_available("configured") is False

    assert choices == [("configured", ("available",))]
    assert downloads == pulls == []


def test_configured_download_choice_prompts_and_starts_pull() -> None:
    workspace = WorkspaceStub(models=("available",))
    controller, _, downloads, _, pulls, _ = make_controller(
        workspace, selected="configured", confirm_download=True
    )

    assert controller.ensure_available("configured") is False

    assert downloads == ["configured"]
    assert pulls == ["configured"]


def test_no_installed_models_can_decline_download() -> None:
    workspace = WorkspaceStub()
    controller, choices, downloads, _, pulls, _ = make_controller(workspace)

    assert controller.ensure_available("configured") is False

    assert choices == []
    assert downloads == ["configured"]
    assert pulls == []
