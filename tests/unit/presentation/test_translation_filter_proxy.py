import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.presentation.translation_filter_proxy import TranslationFilterProxyModel
from locaforge.presentation.translation_table_model import TranslationTableModel


def make_proxy() -> TranslationFilterProxyModel:
    source_model = TranslationTableModel()
    source_model.set_entries(
        [
            TranslationEntry("one", ("dialog", "hello"), "Hello"),
            TranslationEntry(
                "two",
                ("menu", "exit"),
                "Exit",
                translation="Выход",
                status=EntryStatus.TRANSLATED,
                context="main-menu",
            ),
        ]
    )
    proxy = TranslationFilterProxyModel()
    proxy.setSourceModel(source_model)
    return proxy


def test_proxy_filters_by_text_and_status() -> None:
    application = QApplication.instance() or QApplication([])
    proxy = make_proxy()

    proxy.set_search_text("menu")
    assert proxy.rowCount() == 1
    proxy.set_search_text("")
    proxy.set_status("untranslated")

    assert application is not None
    assert proxy.rowCount() == 1
    assert proxy.data(proxy.index(0, 1)) == "Hello"


def test_proxy_filters_by_multiple_statuses() -> None:
    application = QApplication.instance() or QApplication([])
    proxy = make_proxy()

    proxy.set_statuses({"untranslated", "translated"})

    assert application is not None
    assert proxy.rowCount() == 2


def test_proxy_filters_by_entry_context() -> None:
    application = QApplication.instance() or QApplication([])
    proxy = make_proxy()

    proxy.set_search_text("main-menu")

    assert application is not None
    assert proxy.rowCount() == 1
    assert proxy.data(proxy.index(0, 0)) == "menu/exit"


def test_proxy_limits_text_search_to_selected_field() -> None:
    application = QApplication.instance() or QApplication([])
    proxy = make_proxy()

    proxy.set_search_field("source")
    proxy.set_search_text("menu")
    assert proxy.rowCount() == 0

    proxy.set_search_field("context")
    assert application is not None
    assert proxy.rowCount() == 1


def test_proxy_filters_by_validation_issue_entry_ids() -> None:
    application = QApplication.instance() or QApplication([])
    proxy = make_proxy()

    proxy.set_issue_entry_ids({"two"})

    assert application is not None
    assert proxy.rowCount() == 1
    assert proxy.data(proxy.index(0, 0)) == "menu/exit"

    proxy.set_issue_entry_ids(None)

    assert proxy.rowCount() == 2


def test_proxy_combines_issue_and_status_filters() -> None:
    application = QApplication.instance() or QApplication([])
    proxy = make_proxy()

    proxy.set_issue_entry_ids({"one", "two"})
    proxy.set_status("translated")

    assert application is not None
    assert proxy.rowCount() == 1
    assert proxy.data(proxy.index(0, 0)) == "menu/exit"


def test_proxy_filters_by_project_document() -> None:
    application = QApplication.instance() or QApplication([])
    proxy = make_proxy()
    source = proxy.sourceModel()
    assert isinstance(source, TranslationTableModel)
    source.entry_at(0).document_id = "menus"
    source.entry_at(1).document_id = "dialogs"

    proxy.set_document_id("dialogs")

    assert application is not None
    assert proxy.rowCount() == 1
    assert proxy.data(proxy.index(0, 0)) == "menu/exit"


def test_proxy_sorts_statuses_by_translation_workflow() -> None:
    application = QApplication.instance() or QApplication([])
    proxy = make_proxy()

    proxy.sort(3, Qt.SortOrder.AscendingOrder)

    assert application is not None
    assert proxy.data(proxy.index(0, 3)) == "Untranslated"
    assert proxy.data(proxy.index(1, 3)) == "Translated"


def test_proxy_uses_refreshed_search_cache_after_entry_update() -> None:
    application = QApplication.instance() or QApplication([])
    proxy = make_proxy()
    source = proxy.sourceModel()
    assert isinstance(source, TranslationTableModel)
    proxy.set_search_field("translation")
    proxy.set_search_text("сохранить")
    assert proxy.rowCount() == 0

    source.update_entry(
        TranslationEntry(
            "one",
            ("dialog", "hello"),
            "Hello",
            translation="Сохранить",
            status=EntryStatus.TRANSLATED,
        )
    )

    assert application is not None
    assert proxy.rowCount() == 1
    assert proxy.data(proxy.index(0, 2)) == "Сохранить"
