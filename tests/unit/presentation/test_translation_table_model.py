import os

import pytest

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
    assert model.data(model.index(0, 3)) == "Needs review"
    assert model.data(model.index(0, 3), model.status_role) == "needs_review"


def test_table_model_updates_last_entry_by_id() -> None:
    application = QApplication.instance() or QApplication([])
    model = TranslationTableModel()
    model.set_entries(
        [
            TranslationEntry(f"entry-{index}", ("text", index), f"Source {index}")
            for index in range(10_000)
        ]
    )
    updated = TranslationEntry(
        "entry-9999",
        ("text", 9999),
        "Source 9999",
        translation="Updated",
        status=EntryStatus.NEEDS_REVIEW,
    )

    model.update_entry(updated)

    assert application is not None
    assert model.entry_at(9_999) is updated


def test_table_model_rejects_duplicate_entry_ids() -> None:
    application = QApplication.instance() or QApplication([])
    model = TranslationTableModel()

    with pytest.raises(ValueError, match="Duplicate table entry id"):
        model.set_entries(
            [
                TranslationEntry("entry-1", ("first",), "Hello"),
                TranslationEntry("entry-1", ("second",), "Goodbye"),
            ]
        )

    assert application is not None
    assert model.rowCount() == 0


def test_table_model_caches_normalized_search_values_and_refreshes_them() -> None:
    application = QApplication.instance() or QApplication([])
    model = TranslationTableModel()
    model.set_entries(
        [
            TranslationEntry(
                "entry-1",
                ("Menus", "Start"),
                "START GAME",
                translation="НАЧАТЬ ИГРУ",
                context="MAIN MENU",
            )
        ]
    )

    assert model.search_values_at(0) == (
        "menus/start",
        "start game",
        "начать игру",
        "main menu",
    )

    model.update_entry(
        TranslationEntry(
            "entry-1",
            ("Menus", "Start"),
            "START GAME",
            translation="ИГРАТЬ",
            context="TITLE SCREEN",
        )
    )

    assert application is not None
    assert model.search_values_at(0) == (
        "menus/start",
        "start game",
        "играть",
        "title screen",
    )
