from types import SimpleNamespace
from typing import Any, cast

from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.presentation.entry_action_runner import EntryActionRunner


def entry(entry_id: str = "entry-1") -> TranslationEntry:
    return TranslationEntry(
        id=entry_id,
        key_path=(entry_id,),
        source="Hello",
        translation="Привет",
        status=EntryStatus.TRANSLATED,
    )


class WorkspaceStub:
    def __init__(self, entries, *, has_project: bool = True) -> None:
        self.has_project = has_project
        self.project = SimpleNamespace(entries=list(entries))


def make_runner(
    workspace: WorkspaceStub,
    *,
    busy: bool = False,
    current_entry: str | None = "entry-1",
):
    events: list[object] = []
    errors: list[str] = []
    runner = EntryActionRunner(
        cast(Any, workspace),
        is_busy=lambda: busy,
        current_entry_id=lambda: current_entry,
        invalidate_memory=lambda: events.append("invalidate-memory"),
        update_entry=lambda value: events.append(("update-entry", value.id)),
        update_filter_entries=lambda values: events.append(
            ("filter-entries", tuple(value.id for value in values))
        ),
        update_project_title=lambda: events.append("title"),
        schedule_summary_refresh=lambda: events.append("summary"),
        refresh_memory=lambda entry_id: events.append(("refresh-memory", entry_id)),
        sync_autosave=lambda: events.append("autosave"),
        show_status=lambda message, timeout: events.append(
            ("status", message, timeout)
        ),
        show_error=errors.append,
    )
    return runner, events, errors


def test_success_updates_entry_surfaces_in_order() -> None:
    updated = entry()
    workspace = WorkspaceStub((updated,))
    runner, events, errors = make_runner(workspace)

    result = runner.run(lambda: updated, "Translation updated")

    assert result is True
    assert events == [
        "invalidate-memory",
        ("update-entry", "entry-1"),
        ("filter-entries", ("entry-1",)),
        "title",
        "summary",
        ("refresh-memory", "entry-1"),
        "autosave",
        ("status", "Translation updated", 5000),
    ]
    assert errors == []


def test_noncurrent_entry_skips_memory_refresh() -> None:
    updated = entry("entry-2")
    runner, events, _ = make_runner(
        WorkspaceStub((updated,)), current_entry="entry-1"
    )

    assert runner.run(lambda: updated, "Updated") is True

    assert ("refresh-memory", "entry-2") not in events
    assert "autosave" in events


def test_closed_workspace_passes_empty_entries_to_filters() -> None:
    updated = entry()
    runner, events, _ = make_runner(
        WorkspaceStub((updated,), has_project=False)
    )

    assert runner.run(lambda: updated, "Updated") is True

    assert ("filter-entries", ()) in events


def test_busy_state_rejects_entry_action() -> None:
    updated = entry()
    runner, events, errors = make_runner(WorkspaceStub((updated,)), busy=True)

    assert runner.run(lambda: updated, "Updated") is False

    assert events == []
    assert errors == []


def test_action_error_is_reported_without_post_action_updates() -> None:
    updated = entry()
    runner, events, errors = make_runner(WorkspaceStub((updated,)))

    def fail() -> TranslationEntry:
        events.append("action")
        raise ValueError("locked entry")

    assert runner.run(fail, "Updated") is False

    assert events == ["action"]
    assert errors == ["locked entry"]
