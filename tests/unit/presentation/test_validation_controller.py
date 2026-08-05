from __future__ import annotations

from typing import Any, cast

from locaforge.application.dto.validation import ProjectValidationResult
from locaforge.presentation.validation_controller import ValidationController


def make_controller() -> tuple[ValidationController, dict[str, list[object]]]:
    calls: dict[str, list[object]] = {
        "busy": [],
        "refresh": [],
        "autosave": [],
        "cancel": [],
        "status": [],
        "error": [],
    }
    controller = ValidationController(
        workspace=cast(Any, object()),
        set_busy=lambda busy, refresh: calls["busy"].append((busy, refresh)),
        refresh_project=lambda select_first: calls["refresh"].append(select_first),
        sync_autosave=lambda: calls["autosave"].append(True),
        disable_cancel=lambda: calls["cancel"].append("disabled"),
        show_status=lambda message, timeout: calls["status"].append((message, timeout)),
        show_error=lambda title, message: calls["error"].append((title, message)),
    )
    return controller, calls


def test_successful_validation_refreshes_and_schedules_autosave() -> None:
    controller, calls = make_controller()

    controller._validation_succeeded(ProjectValidationResult(12, 3))

    assert calls["busy"] == [(False, False)]
    assert calls["refresh"] == [False]
    assert calls["autosave"] == [True]
    assert calls["status"] == [
        ("Project validation completed: 12 checked, 3 with issues", 5000)
    ]


def test_invalid_result_does_not_refresh_or_autosave() -> None:
    controller, calls = make_controller()

    controller._validation_succeeded(object())

    assert calls["error"] == [("Validation", "Worker returned an invalid result")]
    assert calls["refresh"] == []
    assert calls["autosave"] == []


def test_failure_restores_ui_and_reports_error() -> None:
    controller, calls = make_controller()

    controller._validation_failed("Invalid database")

    assert calls["busy"] == [(False, True)]
    assert calls["error"] == [("Validation failed", "Invalid database")]
