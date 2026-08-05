from __future__ import annotations

from typing import Any, cast

from locaforge.application.dto.review import ReviewBatchResult
from locaforge.presentation.review_controller import ReviewController


def make_controller() -> tuple[ReviewController, dict[str, list[object]]]:
    calls: dict[str, list[object]] = {
        "busy": [],
        "refresh": [],
        "autosave": [],
        "status": [],
        "error": [],
        "progress": [],
    }
    controller = ReviewController(
        workspace=cast(Any, object()),
        ensure_model=lambda model, reviewer: True,
        set_busy=lambda busy, refresh: calls["busy"].append((busy, refresh)),
        refresh_project=lambda select_first: calls["refresh"].append(select_first),
        sync_autosave=lambda: calls["autosave"].append(True),
        show_status=lambda message, timeout: calls["status"].append((message, timeout)),
        show_error=lambda title, message: calls["error"].append((title, message)),
        show_progress=lambda completed, total: calls["progress"].append(
            (completed, total)
        ),
    )
    return controller, calls


def test_successful_review_refreshes_and_schedules_autosave() -> None:
    controller, calls = make_controller()

    controller._review_succeeded(ReviewBatchResult(4, 2))

    assert calls["busy"] == [(False, False)]
    assert calls["refresh"] == [False]
    assert calls["autosave"] == [True]
    assert calls["status"] == [("AI review completed: 2 issue(s)", 5000)]


def test_cancelled_review_reports_partial_progress() -> None:
    controller, calls = make_controller()

    controller._review_succeeded(ReviewBatchResult(3, 1, cancelled=True))

    assert calls["status"] == [("AI review cancelled after 3 entries", 5000)]


def test_invalid_result_is_reported_without_refreshing() -> None:
    controller, calls = make_controller()

    controller._review_succeeded(object())

    assert calls["error"] == [("AI review", "Worker returned an invalid result")]
    assert calls["refresh"] == []
    assert calls["autosave"] == []


def test_failure_restores_ui_and_reports_error() -> None:
    controller, calls = make_controller()

    controller._review_failed("Ollama unavailable")

    assert calls["busy"] == [(False, True)]
    assert calls["error"] == [("AI review failed", "Ollama unavailable")]


def test_progress_is_forwarded_to_ui() -> None:
    controller, calls = make_controller()

    controller._review_progress(2, 5)

    assert calls["progress"] == [(2, 5)]
