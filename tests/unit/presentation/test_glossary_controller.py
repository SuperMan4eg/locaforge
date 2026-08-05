import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QListWidget, QPushButton, QWidget

from locaforge.domain.glossary import GlossaryTerm
from locaforge.presentation.glossary_controller import GlossaryController


class WorkspaceStub:
    has_project = True

    def __init__(self) -> None:
        self.exported_to: Path | None = None

    def glossary_terms(self) -> tuple[GlossaryTerm, ...]:
        return (
            GlossaryTerm("en", "ru", "Save", "Сохранить", case_sensitive=True),
        )

    def export_glossary_csv(self, destination: Path) -> None:
        self.exported_to = destination


def make_controller() -> tuple[
    GlossaryController,
    WorkspaceStub,
    QListWidget,
    tuple[QPushButton, QPushButton, QPushButton, QPushButton],
    list[str],
    QWidget,
]:
    parent = QWidget()
    terms = QListWidget(parent)
    buttons = tuple(QPushButton(parent) for _ in range(4))
    messages: list[str] = []
    workspace = WorkspaceStub()

    def run(action: Callable[[], object], message: str) -> bool:
        action()
        messages.append(message)
        return True

    controller = GlossaryController(
        workspace=cast(Any, workspace),
        terms=terms,
        add_button=buttons[0],
        remove_button=buttons[1],
        import_button=buttons[2],
        export_button=buttons[3],
        run_action=run,
        source_text=lambda: "Save",
        translation_text=lambda: "Сохранить",
        is_busy=lambda: False,
        parent=parent,
    )
    return controller, workspace, terms, buttons, messages, parent


def test_refresh_displays_terms_and_selection_enables_remove() -> None:
    application = QApplication.instance() or QApplication([])
    controller, _, terms, buttons, _, parent = make_controller()

    controller.refresh()
    controller.set_enabled(True)
    terms.setCurrentRow(0)

    assert application is not None
    assert parent is not None
    assert terms.item(0).text() == "Save -> Сохранить [case-sensitive]"
    assert buttons[1].isEnabled() is True


def test_disabling_controller_disables_all_actions() -> None:
    application = QApplication.instance() or QApplication([])
    controller, _, terms, buttons, _, parent = make_controller()
    controller.refresh()
    terms.setCurrentRow(0)

    controller.set_enabled(False)

    assert application is not None
    assert parent is not None
    assert all(button.isEnabled() is False for button in buttons)


def test_export_adds_csv_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = QApplication.instance() or QApplication([])
    controller, workspace, _, _, messages, parent = make_controller()
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args: ("terms.backup", "CSV files (*.csv)"),
    )

    controller.export_csv()

    assert application is not None
    assert parent is not None
    assert workspace.exported_to == Path("terms.csv")
    assert messages == ["Glossary CSV exported"]
