from locaforge.presentation.project_action_runner import ProjectActionRunner


def make_runner(*, busy: bool = False):
    events: list[object] = []
    errors: list[str] = []
    runner = ProjectActionRunner(
        is_busy=lambda: busy,
        refresh_project=lambda: events.append("refresh"),
        sync_autosave=lambda: events.append("autosave"),
        show_status=lambda message, timeout: events.append(
            ("status", message, timeout)
        ),
        show_error=errors.append,
    )
    return runner, events, errors


def test_success_runs_action_then_refresh_autosave_and_status() -> None:
    runner, events, errors = make_runner()

    result = runner.run(lambda: events.append("action"), "Project updated")

    assert result is True
    assert events == [
        "action",
        "refresh",
        "autosave",
        ("status", "Project updated", 5000),
    ]
    assert errors == []


def test_busy_state_rejects_action_without_side_effects() -> None:
    runner, events, errors = make_runner(busy=True)

    result = runner.run(lambda: events.append("action"), "Project updated")

    assert result is False
    assert events == []
    assert errors == []


def test_action_error_is_reported_without_success_side_effects() -> None:
    runner, events, errors = make_runner()

    def fail() -> None:
        events.append("action")
        raise ValueError("invalid operation")

    result = runner.run(fail, "Project updated")

    assert result is False
    assert events == ["action"]
    assert errors == ["invalid operation"]
