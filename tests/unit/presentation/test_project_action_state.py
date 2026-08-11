import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow

from locaforge.presentation.edit_actions import build_edit_actions
from locaforge.presentation.project_action_state import (
    ProjectActionState,
    ProjectActionStateRenderer,
)


def test_renders_idle_project_selection_format_and_history_state() -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    calls: list[tuple[str, bool]] = []
    try:
        edit = build_edit_actions(
            window,
            undo=lambda: None,
            redo=lambda: None,
            open_application_settings=lambda: None,
        )
        idle = QAction(window)
        project = QAction(window)
        selected = QAction(window)
        json_export = QAction(window)
        po_export = QAction(window)
        reset = QAction(window)
        renderer = ProjectActionStateRenderer(
            edit_actions=edit,
            idle_targets=(idle,),
            project_targets=(project,),
            selected_document_targets=(selected,),
            format_export_targets={"json": json_export, "po": po_export},
            reset_disabled_targets=(reset,),
            set_issues_enabled=lambda enabled: calls.append(("issues", enabled)),
            set_glossary_enabled=lambda enabled: calls.append(("glossary", enabled)),
        )

        renderer.render(
            ProjectActionState(
                has_project=True,
                busy=False,
                has_selected_documents=True,
                source_format="json",
                undo_label="Edit translation",
                can_undo=True,
                redo_label="Review translations",
                can_redo=True,
            )
        )

        assert idle.isEnabled() is True
        assert project.isEnabled() is True
        assert selected.isEnabled() is True
        assert json_export.isEnabled() is True
        assert po_export.isEnabled() is False
        assert reset.isEnabled() is False
        assert edit.undo.text() == "Undo Edit translation"
        assert edit.undo.isEnabled() is True
        assert edit.redo.text() == "Redo Review translations"
        assert edit.redo.isEnabled() is True
        assert calls == [("issues", True), ("glossary", True)]
    finally:
        window.close()
        application.processEvents()


def test_busy_state_disables_idle_and_project_commands_and_resets_labels() -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    try:
        edit = build_edit_actions(
            window,
            undo=lambda: None,
            redo=lambda: None,
            open_application_settings=lambda: None,
        )
        idle = QAction(window)
        project = QAction(window)
        renderer = ProjectActionStateRenderer(
            edit_actions=edit,
            idle_targets=(idle,),
            project_targets=(project,),
            selected_document_targets=(),
            format_export_targets={},
            reset_disabled_targets=(),
            set_issues_enabled=lambda _enabled: None,
            set_glossary_enabled=lambda _enabled: None,
        )

        renderer.render(
            ProjectActionState(False, True, False, None)
        )

        assert idle.isEnabled() is False
        assert project.isEnabled() is False
        assert edit.undo.text() == "Undo last operation"
        assert edit.undo.isEnabled() is False
        assert edit.redo.text() == "Redo last operation"
        assert edit.redo.isEnabled() is False
    finally:
        window.close()
        application.processEvents()
