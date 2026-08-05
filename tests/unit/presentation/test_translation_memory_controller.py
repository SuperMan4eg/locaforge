import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from typing import Any, cast

from PySide6.QtWidgets import QApplication, QListWidget, QPushButton, QWidget

from locaforge.domain.translation_memory import TranslationMemoryMatch, TranslationMemoryRecord
from locaforge.presentation.translation_memory_controller import (
    TranslationMemoryController,
)


def make_controller() -> tuple[
    TranslationMemoryController,
    QListWidget,
    QPushButton,
    list[str],
    QWidget,
]:
    parent = QWidget()
    suggestions = QListWidget(parent)
    apply_button = QPushButton(parent)
    applied: list[str] = []
    controller = TranslationMemoryController(
        workspace=cast(Any, object()),
        suggestions=suggestions,
        apply_button=apply_button,
        can_apply=lambda: True,
        apply_suggestion=lambda: applied.append("applied"),
        parent=parent,
        debounce_ms=10_000,
    )
    return controller, suggestions, apply_button, applied, parent


def match(translation: str = "Сохранить") -> TranslationMemoryMatch:
    return TranslationMemoryMatch(
        TranslationMemoryRecord("en", "ru", "Save", translation, context="menu"),
        0.95,
    )


def test_matching_result_is_displayed_and_can_be_applied() -> None:
    application = QApplication.instance() or QApplication([])
    controller, suggestions, apply_button, applied, parent = make_controller()
    controller.refresh("entry-one")

    controller._matches_loaded("entry-one", 1, (match(),))

    assert application is not None
    assert parent is not None
    assert suggestions.count() == 1
    assert "95% | Save [menu]" in suggestions.item(0).text()
    assert controller.suggestion == "Сохранить"
    assert apply_button.isEnabled() is True

    apply_button.click()

    assert applied == ["applied"]


def test_stale_result_is_ignored() -> None:
    application = QApplication.instance() or QApplication([])
    controller, suggestions, _, _, parent = make_controller()
    controller.refresh("entry-one")
    controller.refresh("entry-two")

    controller._matches_loaded("entry-one", 1, (match(),))

    assert application is not None
    assert parent is not None
    assert suggestions.count() == 0
    assert controller.suggestion is None


def test_cached_result_is_reused_without_pending_lookup() -> None:
    application = QApplication.instance() or QApplication([])
    controller, suggestions, _, _, parent = make_controller()
    controller.refresh("entry-one")
    controller._matches_loaded("entry-one", 1, (match("Записать"),))

    controller.clear()
    controller.refresh("entry-one")

    assert application is not None
    assert parent is not None
    assert suggestions.count() == 1
    assert controller.suggestion == "Записать"


def test_clear_resets_pending_selection_and_button() -> None:
    application = QApplication.instance() or QApplication([])
    controller, suggestions, apply_button, _, parent = make_controller()
    controller.refresh("entry-one")
    controller._matches_loaded("entry-one", 1, (match(),))

    controller.clear()

    assert application is not None
    assert parent is not None
    assert suggestions.count() == 0
    assert controller.suggestion is None
    assert apply_button.isEnabled() is False
