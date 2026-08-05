import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.presentation.translation_table_model import TranslationTableModel


def test_table_model_exposes_translation_entry_columns() -> None:
    application = QApplication.instance() or QApplication([])
    model = TranslationTableModel()
    model.set_entries(
        [
            TranslationEntry(
                "entry-1",
                ("dialog", 0, "text"),
                "Hello",
                translation="Привет",
                status=EntryStatus.TRANSLATED,
            )
        ]
    )

    assert application is not None
    assert model.rowCount() == 1
    assert model.columnCount() == 4
    assert model.data(model.index(0, 0)) == "dialog/0/text"
    assert model.data(model.index(0, 2)) == "Привет"
    assert model.headerData(3, Qt.Orientation.Horizontal) == "Status"


def test_table_model_updates_one_entry_without_resetting_rows() -> None:
    application = QApplication.instance() or QApplication([])
    model = TranslationTableModel()
    model.set_entries([TranslationEntry("entry-1", ("text",), "Hello")])
    updated = TranslationEntry(
        "entry-1",
        ("text",),
        "Hello",
        translation="Привет",
        status=EntryStatus.NEEDS_REVIEW,
    )

    model.update_entry(updated)

    assert application is not None
    assert model.rowCount() == 1
    assert model.entry_at(0) == updated
    assert model.data(model.index(0, 3)) == "needs_review"
