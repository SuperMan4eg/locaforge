from typing import Any, cast

from locaforge.domain.settings import ModelSettings
from locaforge.presentation.application_settings import ApplicationSettings
from locaforge.presentation.application_settings_controller import (
    ApplicationSettingsController,
)


class WorkspaceStub:
    def __init__(self) -> None:
        self.model_settings: list[ModelSettings] = []

    def set_global_model_settings(self, settings: ModelSettings) -> None:
        self.model_settings.append(settings)


class StoreStub:
    def __init__(self) -> None:
        self.saved: list[ApplicationSettings] = []

    def save(self, settings: ApplicationSettings) -> None:
        self.saved.append(settings)


def make_controller(*, localization: bool = True):
    workspace = WorkspaceStub()
    store = StoreStub()
    current: list[ApplicationSettings] = []
    servers: list[str] = []
    locales: list[str] = []
    retranslations: list[bool] = []
    delays: list[int] = []
    visuals: list[bool] = []
    syncs: list[bool] = []
    saved_notifications: list[bool] = []
    controller = ApplicationSettingsController(
        cast(Any, workspace),
        cast(Any, store),
        set_current_settings=current.append,
        configure_ollama_server=servers.append,
        set_locale=locales.append if localization else None,
        retranslate=lambda: retranslations.append(True),
        set_autosave_delay=delays.append,
        apply_visual_settings=lambda: visuals.append(True),
        sync_autosave=lambda: syncs.append(True),
        show_saved=lambda: saved_notifications.append(True),
    )
    return (
        controller,
        workspace,
        store,
        current,
        servers,
        locales,
        retranslations,
        delays,
        visuals,
        syncs,
        saved_notifications,
    )


def test_apply_updates_all_runtime_settings_components() -> None:
    results = make_controller()
    controller, workspace, store, current, servers, locales = results[:6]
    retranslations, delays, visuals, syncs, notifications = results[6:]
    settings = ApplicationSettings(
        ui_locale="ru-RU",
        theme="dark",
        autosave_delay_seconds=7,
        ollama_server_url="http://ollama:11434",
        model_settings=ModelSettings(model="qwen-new"),
    )

    controller.apply(settings)

    assert current == [settings]
    assert workspace.model_settings == [settings.model_settings]
    assert servers == ["http://ollama:11434"]
    assert store.saved == [settings]
    assert locales == ["ru-RU"]
    assert retranslations == [True]
    assert delays == [7000]
    assert visuals == [True]
    assert syncs == [True]
    assert notifications == [True]


def test_apply_without_localization_skips_locale_and_retranslate() -> None:
    results = make_controller(localization=False)
    controller = results[0]
    locales = results[5]
    retranslations = results[6]

    controller.apply(ApplicationSettings(ui_locale="de-DE"))

    assert locales == []
    assert retranslations == []
    assert results[7] == [2000]
    assert results[8] == [True]
    assert results[9] == [True]
    assert results[10] == [True]


def test_restore_ollama_server_only_reconfigures_client() -> None:
    results = make_controller()
    controller = results[0]
    workspace = results[1]
    store = results[2]
    current = results[3]
    servers = results[4]

    controller.restore_ollama_server("http://original:11434")

    assert servers == ["http://original:11434"]
    assert workspace.model_settings == []
    assert store.saved == []
    assert current == []
