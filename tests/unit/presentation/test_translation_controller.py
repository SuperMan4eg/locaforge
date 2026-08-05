from __future__ import annotations

from typing import Any, cast

from locaforge.application.dto.translation import BatchResult
from locaforge.presentation.translation_controller import TranslationController


def make_controller() -> tuple[TranslationController, dict[str, list[object]]]:
    calls: dict[str, list[object]] = {
        "busy": [],
        "refresh": [],
        "autosave": [],
        "status": [],
        "error": [],
        "warning": [],
        "progress": [],
    }
    controller = TranslationController(
        workspace=cast(Any, object()),
        ensure_model=lambda model: True,
        set_busy=lambda busy, refresh: calls["busy"].append((busy, refresh)),
        refresh_project=lambda select_first: calls["refresh"].append(select_first),
        sync_autosave=lambda: calls["autosave"].append(True),
        show_status=lambda message, timeout: calls["status"].append((message, timeout)),
        show_error=lambda title, message: calls["error"].append((title, message)),
        show_warning=lambda title, message: calls["warning"].append((title, message)),
        show_progress=lambda completed, total: calls["progress"].append(
            (completed, total)
        ),
    )
    return controller, calls


def test_successful_translation_refreshes_and_schedules_autosave() -> None:
    controller, calls = make_controller()

    controller._translation_succeeded(BatchResult(("one", "two"), (), ()))

    assert calls["busy"] == [(False, False)]
    assert calls["refresh"] == [False]
    assert calls["autosave"] == [True]
    assert calls["status"] == [("Translated 2 entries", 5000)]


def test_cancelled_translation_reports_completed_count() -> None:
    controller, calls = make_controller()

    controller._translation_succeeded(BatchResult(("one",), (), (), cancelled=True))

    assert calls["status"] == [
        ("Translation cancelled after 1 completed entries", 5000)
    ]


def test_partial_errors_are_reported_after_success() -> None:
    controller, calls = make_controller()

    controller._translation_succeeded(
        BatchResult(("one",), (), ("two: timeout", "three: invalid response"))
    )

    assert calls["warning"] == [
        (
            "Batch translation completed with errors",
            "two: timeout\nthree: invalid response",
        )
    ]
    assert calls["autosave"] == [True]


def test_invalid_result_and_failure_are_reported() -> None:
    controller, calls = make_controller()

    controller._translation_succeeded(object())
    controller._translation_failed("Ollama unavailable")

    assert calls["error"] == [
        ("Batch translation", "Worker returned an invalid result"),
        ("Batch translation failed", "Ollama unavailable"),
    ]
    assert calls["refresh"] == []
    assert calls["autosave"] == []


def test_progress_is_forwarded_to_ui() -> None:
    controller, calls = make_controller()

    controller._translation_progress(2, 7)

    assert calls["progress"] == [(2, 7)]
