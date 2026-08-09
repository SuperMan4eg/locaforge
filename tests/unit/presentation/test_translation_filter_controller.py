import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from locaforge.domain.document import ProjectDocument
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.presentation.translation_filter_controller import (
    TranslationFilterController,
)
from locaforge.presentation.translation_filter_proxy import TranslationFilterProxyModel
from locaforge.presentation.translation_table_model import TranslationTableModel


def make_controller() -> tuple[
    TranslationFilterController,
    TranslationTableModel,
    TranslationFilterProxyModel,
    QWidget,
]:
    source_model = TranslationTableModel()
    source_model.set_entries(
        [
            TranslationEntry("one", ("hello",), "Hello"),
            TranslationEntry(
                "two",
                ("exit",),
                "Exit",
                translation="Выход",
                status=EntryStatus.TRANSLATED,
            ),
        ]
    )
    proxy_model = TranslationFilterProxyModel()
    proxy_model.setSourceModel(source_model)
    parent = QWidget()
    controller = TranslationFilterController(source_model, proxy_model, parent)
    return controller, source_model, proxy_model, parent


def test_issue_filter_and_clear_are_coordinated() -> None:
    application = QApplication.instance() or QApplication([])
    controller, _, proxy, parent = make_controller()

    controller.set_issue_entries({"two"})
    controller.set_issues_only(True)

    assert application is not None
    assert parent is not None
    assert proxy.rowCount() == 1
    assert controller.issues_button.text() == "Issues only (1)"
    assert controller.clear_button.isEnabled() is True

    controller.clear()

    assert proxy.rowCount() == 2
    assert controller.clear_button.isEnabled() is False


def test_status_filter_uses_stable_label_after_counts_are_added() -> None:
    application = QApplication.instance() or QApplication([])
    controller, source, proxy, parent = make_controller()
    controller.update_entries([source.entry_at(0), source.entry_at(1)])
    translated_action = controller.status_button.menu().actions()[1]

    translated_action.setChecked(True)
    controller._apply_status_filter()

    assert application is not None
    assert parent is not None
    assert proxy.rowCount() == 1
    assert controller.status_button.text() == "Translated"
    assert translated_action.text() == "Translated (1)"


def test_result_count_tracks_source_and_filtered_rows() -> None:
    application = QApplication.instance() or QApplication([])
    controller, source, _, parent = make_controller()

    controller.update_entries([source.entry_at(0), source.entry_at(1)])
    controller.set_issue_entries({"one"})
    controller.set_issues_only(True)

    assert application is not None
    assert parent is not None
    assert controller.result_count.text() == "1 / 2 entries"


def test_search_field_control_filters_only_selected_column() -> None:
    application = QApplication.instance() or QApplication([])
    controller, _, proxy, parent = make_controller()

    controller.search_field.setCurrentIndex(2)  # Source
    controller.search.setText("exit")
    controller._apply_search_filter()

    assert application is not None
    assert parent is not None
    assert proxy.rowCount() == 1
    assert proxy.data(proxy.index(0, 1)) == "Exit"


def test_document_control_filters_entries_by_file() -> None:
    application = QApplication.instance() or QApplication([])
    controller, source, proxy, parent = make_controller()
    source.entry_at(0).document_id = "menus"
    source.entry_at(1).document_id = "dialogs"
    controller.update_documents(
        (
            ProjectDocument("menus", "menus.json", "menus.json", "json", {}),
            ProjectDocument("dialogs", "dialogs.json", "dialogs.json", "json", {}),
        )
    )

    controller.document.setCurrentIndex(2)

    assert application is not None
    assert parent is not None
    assert proxy.rowCount() == 1
    assert proxy.data(proxy.index(0, 1)) == "Exit"
