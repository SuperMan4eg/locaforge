import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow

from locaforge.presentation.review_actions import build_review_actions


def test_builds_review_menu_in_workflow_order_and_connects_callbacks() -> None:
    application = QApplication.instance() or QApplication([])
    window = QMainWindow()
    calls: list[str] = []

    def callback(name: str):
        return lambda: calls.append(name)

    try:
        actions = build_review_actions(
            window,
            select_qa_entries=callback("select"),
            retranslate_qa_entries=callback("retranslate"),
            dismiss_selected_ai_issues=callback("dismiss"),
            review_selected=callback("review-selected"),
            review_all=callback("review-all"),
            approve_selected=callback("approve"),
            reopen_selected=callback("reopen"),
            lock_selected=callback("lock"),
            unlock_selected=callback("unlock"),
        )

        assert [
            action.text()
            for action in actions.menu.actions()
            if not action.isSeparator()
        ] == [
            "Select all QA entries",
            "Re-translate all QA entries",
            "Dismiss AI issues for selected",
            "AI review selected",
            "AI review all Needs review",
            "Approve selected",
            "Reopen selected",
            "Lock selected",
            "Unlock selected",
        ]
        actions.review_selected.trigger()
        actions.approve_selected.trigger()
        actions.unlock_selected.trigger()
        assert calls == ["review-selected", "approve", "unlock"]
    finally:
        window.close()
        application.processEvents()
