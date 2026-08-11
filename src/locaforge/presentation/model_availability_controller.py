"""Ollama model availability and fallback selection orchestration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace

from locaforge.application.project_workspace import ProjectWorkspace


class ModelAvailabilityController:
    """Ensures a configured translation or review model can be used."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        choose_model: Callable[[str, Sequence[str]], str | None],
        confirm_download: Callable[[str], bool],
        offer_ollama_installation: Callable[[], None],
        start_model_pull: Callable[[str], object],
        set_displayed_model: Callable[[str], None],
    ) -> None:
        self._workspace = workspace
        self._choose_model = choose_model
        self._confirm_download = confirm_download
        self._offer_ollama_installation = offer_ollama_installation
        self._start_model_pull = start_model_pull
        self._set_displayed_model = set_displayed_model

    def ensure_available(self, model: str, reviewer: bool = False) -> bool:
        try:
            installed_models = self._workspace.list_models()
        except Exception:
            self._offer_ollama_installation()
            return False
        if model in installed_models:
            return True
        if installed_models:
            selected = self._choose_model(model, installed_models)
            if selected is None:
                return False
            if selected != model:
                settings = self._workspace.resolve_model_settings()
                updated_settings = (
                    replace(settings, review_model=selected)
                    if reviewer
                    else replace(settings, model=selected)
                )
                self._workspace.update_model_settings(updated_settings)
                self._set_displayed_model(updated_settings.model)
                return True
        if self._confirm_download(model):
            self._start_model_pull(model)
        return False
