import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QStringListModel
from PySide6.QtWidgets import QApplication, QMainWindow

from locaforge.presentation.translation_workspace_widgets import (
    build_translation_workspace_widgets,
)


def test_builds_translation_workspace_and_connects_editor_controls() -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    calls: list[object] = []
    model = QStringListModel(["First", "Second"])
    try:
        widgets = build_translation_workspace_widgets(
            window,
            table_model=model,
            add_filters=lambda layout: calls.append(("filters", layout.count())),
            current_row_changed=lambda current, _previous: calls.append(
                ("row", current.row())
            ),
            select_candidate=lambda candidate: calls.append(("candidate", candidate)),
            refresh_translation_length=lambda: calls.append("length"),
            dismiss_ai_issue=lambda: calls.append("dismiss"),
            retranslate_current=lambda: calls.append("retranslate"),
            apply_to_matches=lambda: calls.append("matches"),
            copy_source=lambda: calls.append("copy"),
            apply_translation=lambda: calls.append("apply"),
            toggle_approval=lambda: calls.append("approve"),
            set_locked=lambda locked: calls.append(("locked", locked)),
            translate_selected=lambda: calls.append("translate"),
            cancel_translation=lambda: calls.append("cancel"),
        )

        assert widgets.content.count() == 2
        assert widgets.table.model() is model
        assert widgets.table.isSortingEnabled() is True
        assert widgets.source_editor.isReadOnly() is True
        assert widgets.model_candidate.isReadOnly() is True
        assert widgets.reviewer_candidate.isReadOnly() is True
        assert widgets.lock_button.isCheckable() is True
        assert widgets.cancel_button.isVisible() is False
        assert widgets.progress.minimum() == 0
        assert widgets.progress.maximum() == 1

        widgets.translation_editor.setPlainText("Translation")
        widgets.use_model_candidate_button.click()
        widgets.use_reviewer_candidate_button.click()
        widgets.dismiss_ai_issue_button.click()
        widgets.retranslate_button.click()
        widgets.apply_matching_button.click()
        widgets.copy_source_button.click()
        widgets.apply_button.click()
        widgets.approve_button.click()
        widgets.lock_button.click()
        widgets.translate_button.click()
        widgets.cancel_button.click()

        assert calls == [
            ("filters", 0),
            "length",
            ("candidate", "model"),
            ("candidate", "reviewer"),
            "dismiss",
            "retranslate",
            "matches",
            "copy",
            "apply",
            "approve",
            ("locked", True),
            "translate",
            "cancel",
        ]
    finally:
        window.close()
        application.processEvents()
