from __future__ import annotations

from typing import Any, cast

from locaforge.presentation.model_pull_controller import ModelPullController


def make_controller() -> tuple[ModelPullController, dict[str, list[object]]]:
    calls: dict[str, list[object]] = {
        "busy": [],
        "progress": [],
        "status": [],
        "error": [],
    }
    controller = ModelPullController(
        workspace=cast(Any, object()),
        set_busy=lambda busy, refresh: calls["busy"].append((busy, refresh)),
        prepare_progress=lambda: calls["progress"].append("prepared"),
        show_status=lambda message, timeout: calls["status"].append((message, timeout)),
        show_error=lambda title, message: calls["error"].append((title, message)),
    )
    return controller, calls


def test_success_restores_ui_and_reports_installed_model() -> None:
    controller, calls = make_controller()

    controller._model_pull_succeeded("qwen3:8b")

    assert calls["busy"] == [(False, True)]
    assert calls["status"] == [("Ollama model qwen3:8b installed", 5000)]


def test_failure_restores_ui_and_reports_error() -> None:
    controller, calls = make_controller()

    controller._model_pull_failed("disk full")

    assert calls["busy"] == [(False, True)]
    assert calls["error"] == [
        ("Ollama model installation failed", "disk full")
    ]


def test_empty_model_name_is_not_started() -> None:
    controller, calls = make_controller()

    assert controller.start("   ") is False

    assert all(not values for values in calls.values())
