import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtWidgets import QApplication, QMenu

from locaforge.presentation.recent_projects import RecentProjectsStore
from locaforge.presentation.recent_projects_controller import RecentProjectsController


class FakeSettings:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def value(self, key: str) -> object | None:
        return self.values.get(key)

    def setValue(self, key: str, value: object) -> None:
        self.values[key] = value

    def remove(self, key: str) -> None:
        self.values.pop(key, None)


class WorkspaceStub:
    def __init__(self) -> None:
        self.session = SimpleNamespace(container_path=None)
        self.opened: list[Path] = []

    def open(self, path: Path) -> None:
        self.opened.append(path)
        self.session.container_path = path


def make_controller() -> tuple[
    RecentProjectsController,
    WorkspaceStub,
    RecentProjectsStore,
    QMenu,
    list[tuple[str, str]],
]:
    workspace = WorkspaceStub()
    store = RecentProjectsStore(FakeSettings())
    menu = QMenu()
    messages: list[tuple[str, str]] = []

    def run(action: Callable[[], object], message: str) -> bool:
        assert message == "Project opened"
        action()
        return True

    controller = RecentProjectsController(
        workspace=cast(Any, workspace),
        store=store,
        menu=menu,
        run_action=run,
        confirm_unsaved=lambda: True,
        show_info=lambda title, message: messages.append((title, message)),
        parent=menu,
    )
    return controller, workspace, store, menu, messages


def test_empty_menu_has_disabled_placeholder() -> None:
    application = QApplication.instance() or QApplication([])
    controller, _, _, menu, _ = make_controller()

    controller.refresh()

    assert application is not None
    assert len(menu.actions()) == 1
    assert menu.actions()[0].text() == "No recent projects"
    assert menu.actions()[0].isEnabled() is False


def test_missing_project_is_removed_and_reported(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    controller, _, store, menu, messages = make_controller()
    missing = tmp_path / "missing.lfproj"
    store.add(missing)

    assert controller.open(missing) is False

    assert application is not None
    assert store.list_paths() == ()
    assert menu.actions()[0].text() == "No recent projects"
    assert messages[0][0] == "Recent project unavailable"


def test_existing_project_is_opened_and_moved_to_front(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    controller, workspace, store, menu, _ = make_controller()
    project = tmp_path / "project.lfproj"
    project.touch()

    assert controller.open(project) is True

    assert application is not None
    assert workspace.opened == [project]
    assert store.list_paths() == (project.resolve(),)
    assert menu.actions()[0].text().startswith("project.lfproj —")
