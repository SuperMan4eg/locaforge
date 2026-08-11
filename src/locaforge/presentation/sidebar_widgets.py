"""Construction of the main window's docked sidebars."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class SidebarWidgets:
    validation_list: QListWidget
    validation_filter: QComboBox
    history_list: QListWidget
    operation_history_list: QListWidget
    restore_history_button: QPushButton
    log_view: QPlainTextEdit
    copy_diagnostics_button: QPushButton
    translation_memory_list: QListWidget
    apply_memory_button: QPushButton
    glossary_list: QListWidget
    glossary_add_button: QPushButton
    glossary_remove_button: QPushButton
    glossary_import_button: QPushButton
    glossary_export_button: QPushButton
    docks: tuple[QDockWidget, ...]


def build_sidebar_widgets(
    window: QMainWindow,
    *,
    copy_diagnostics: Callable[[], None],
) -> SidebarWidgets:
    """Create, arrange and return all dock-owned widgets."""
    validation_list = QListWidget(window)
    validation_filter = QComboBox(window)
    validation_filter.addItem("All issues", None)
    validation_filter.addItem("Requires attention", "attention")
    validation_filter.addItem("AI Reviewer", "ai_review")
    validation_filter.addItem("Consistency", "consistency")
    validation_filter.addItem("Structural", "structural")
    validation_widget = QWidget(window)
    validation_layout = QVBoxLayout(validation_widget)
    validation_layout.addWidget(validation_filter)
    validation_layout.addWidget(validation_list)
    validation_dock = QDockWidget("Validation", window)
    validation_dock.setObjectName("validation_dock")
    validation_dock.setWidget(validation_widget)
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, validation_dock)

    history_list = QListWidget(window)
    operation_history_list = QListWidget(window)
    restore_history_button = QPushButton("Restore revision", window)
    restore_history_button.setToolTip(
        "Restore the selected earlier translation of the current entry"
    )
    history_widget = QWidget(window)
    history_layout = QVBoxLayout(history_widget)
    history_layout.addWidget(QLabel("Current entry revisions", window))
    history_layout.addWidget(history_list)
    history_layout.addWidget(restore_history_button)
    history_layout.addWidget(QLabel("Recent project operations", window))
    history_layout.addWidget(operation_history_list)
    history_dock = QDockWidget("History", window)
    history_dock.setObjectName("history_dock")
    history_dock.setWidget(history_widget)
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, history_dock)
    window.tabifyDockWidget(validation_dock, history_dock)
    validation_dock.raise_()

    log_view = QPlainTextEdit(window)
    log_view.setReadOnly(True)
    log_view.document().setMaximumBlockCount(1_000)
    clear_log_button = QPushButton("Clear logs", window)
    clear_log_button.setToolTip(
        "Remove all messages currently shown in the log panel"
    )
    clear_log_button.clicked.connect(log_view.clear)
    copy_diagnostics_button = QPushButton("Copy diagnostics", window)
    copy_diagnostics_button.setToolTip(
        "Copy system and project counts without names, paths, or localization content"
    )
    copy_diagnostics_button.clicked.connect(copy_diagnostics)
    log_buttons = QHBoxLayout()
    log_buttons.addWidget(clear_log_button)
    log_buttons.addWidget(copy_diagnostics_button)
    log_widget = QWidget(window)
    log_layout = QVBoxLayout(log_widget)
    log_layout.addWidget(log_view)
    log_layout.addLayout(log_buttons)
    logs_dock = QDockWidget("Logs", window)
    logs_dock.setObjectName("logs_dock")
    logs_dock.setWidget(log_widget)
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, logs_dock)
    window.tabifyDockWidget(history_dock, logs_dock)

    translation_memory_list = QListWidget(window)
    apply_memory_button = QPushButton("Apply TM suggestion", window)
    apply_memory_button.setToolTip(
        "Use the selected translation-memory suggestion for the current entry"
    )
    memory_widget = QWidget(window)
    memory_layout = QVBoxLayout(memory_widget)
    memory_layout.addWidget(translation_memory_list)
    memory_layout.addWidget(apply_memory_button)
    memory_dock = QDockWidget("Translation Memory", window)
    memory_dock.setObjectName("translation_memory_dock")
    memory_dock.setWidget(memory_widget)
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, memory_dock)

    glossary_list = QListWidget(window)
    glossary_add_button = QPushButton("Add term...", window)
    glossary_remove_button = QPushButton("Remove term", window)
    glossary_import_button = QPushButton("Import CSV...", window)
    glossary_export_button = QPushButton("Export CSV...", window)
    glossary_add_button.setToolTip("Add a term for the project's language pair")
    glossary_remove_button.setToolTip("Remove the selected glossary term")
    glossary_import_button.setToolTip("Import glossary terms from a CSV file")
    glossary_export_button.setToolTip("Export glossary terms to a CSV file")
    glossary_buttons = QHBoxLayout()
    glossary_buttons.addWidget(glossary_add_button)
    glossary_buttons.addWidget(glossary_remove_button)
    glossary_buttons.addWidget(glossary_import_button)
    glossary_buttons.addWidget(glossary_export_button)
    glossary_widget = QWidget(window)
    glossary_layout = QVBoxLayout(glossary_widget)
    glossary_layout.addWidget(glossary_list)
    glossary_layout.addLayout(glossary_buttons)
    glossary_dock = QDockWidget("Glossary", window)
    glossary_dock.setObjectName("glossary_dock")
    glossary_dock.setWidget(glossary_widget)
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, glossary_dock)
    window.tabifyDockWidget(memory_dock, glossary_dock)
    memory_dock.raise_()

    return SidebarWidgets(
        validation_list,
        validation_filter,
        history_list,
        operation_history_list,
        restore_history_button,
        log_view,
        copy_diagnostics_button,
        translation_memory_list,
        apply_memory_button,
        glossary_list,
        glossary_add_button,
        glossary_remove_button,
        glossary_import_button,
        glossary_export_button,
        (validation_dock, history_dock, logs_dock, memory_dock, glossary_dock),
    )
