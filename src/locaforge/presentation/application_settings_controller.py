"""Application settings side-effect orchestration."""

from __future__ import annotations

from collections.abc import Callable

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.presentation.application_settings import (
    ApplicationSettings,
    ApplicationSettingsStore,
)


class ApplicationSettingsController:
    """Applies accepted application settings across runtime components."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        settings_store: ApplicationSettingsStore,
        set_current_settings: Callable[[ApplicationSettings], None],
        configure_ollama_server: Callable[[str], None],
        set_locale: Callable[[str], None] | None,
        retranslate: Callable[[], None],
        set_autosave_delay: Callable[[int], None],
        apply_visual_settings: Callable[[], None],
        sync_autosave: Callable[[], None],
        show_saved: Callable[[], None],
    ) -> None:
        self._workspace = workspace
        self._settings_store = settings_store
        self._set_current_settings = set_current_settings
        self._configure_ollama_server = configure_ollama_server
        self._set_locale = set_locale
        self._retranslate = retranslate
        self._set_autosave_delay = set_autosave_delay
        self._apply_visual_settings = apply_visual_settings
        self._sync_autosave = sync_autosave
        self._show_saved = show_saved

    def apply(self, settings: ApplicationSettings) -> None:
        self._set_current_settings(settings)
        self._workspace.set_global_model_settings(settings.model_settings)
        self._configure_ollama_server(settings.ollama_server_url)
        self._settings_store.save(settings)
        if self._set_locale is not None:
            self._set_locale(settings.ui_locale)
            self._retranslate()
        self._set_autosave_delay(settings.autosave_delay_seconds * 1000)
        self._apply_visual_settings()
        self._sync_autosave()
        self._show_saved()

    def restore_ollama_server(self, server_url: str) -> None:
        self._configure_ollama_server(server_url)
