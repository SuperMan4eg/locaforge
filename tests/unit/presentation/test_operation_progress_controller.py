from locaforge.presentation.operation_progress_controller import (
    OperationProgressController,
)


def make_controller():
    events: list[object] = []
    controller = OperationProgressController(
        set_busy_state=lambda busy: events.append(("busy", busy)),
        cancel_autosave=lambda: events.append("cancel-autosave"),
        set_progress_visible=lambda visible: events.append(("progress-visible", visible)),
        set_cancel_visible=lambda visible: events.append(("cancel-visible", visible)),
        set_cancel_enabled=lambda enabled: events.append(("cancel-enabled", enabled)),
        set_progress_range=lambda minimum, maximum: events.append(
            ("range", minimum, maximum)
        ),
        set_progress_value=lambda value: events.append(("value", value)),
        refresh_project=lambda: events.append("refresh"),
        show_status=lambda message: events.append(("status", message)),
    )
    return controller, events


def test_entering_busy_cancels_autosave_shows_controls_and_refreshes() -> None:
    controller, events = make_controller()

    controller.set_busy(True)

    assert events == [
        ("busy", True),
        "cancel-autosave",
        ("progress-visible", True),
        ("cancel-visible", True),
        ("cancel-enabled", True),
        "refresh",
    ]


def test_leaving_busy_hides_controls_resets_progress_and_can_skip_refresh() -> None:
    controller, events = make_controller()

    controller.set_busy(False, refresh=False)

    assert events == [
        ("busy", False),
        ("progress-visible", False),
        ("cancel-visible", False),
        ("cancel-enabled", False),
        ("value", 0),
    ]


def test_translation_progress_updates_range_value_and_status() -> None:
    controller, events = make_controller()

    controller.translation_progress(2, 5)

    assert events == [
        ("range", 0, 5),
        ("value", 2),
        ("status", "Translating 2 of 5"),
    ]


def test_review_progress_uses_nonzero_range_for_empty_total() -> None:
    controller, events = make_controller()

    controller.review_progress(0, 0)

    assert events == [
        ("range", 0, 1),
        ("value", 0),
        ("status", "Reviewing 0 of 0"),
    ]


def test_model_pull_uses_indeterminate_progress_and_disables_cancel() -> None:
    controller, events = make_controller()

    controller.prepare_model_pull()

    assert events == [("cancel-enabled", False), ("range", 0, 0)]
