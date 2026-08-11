"""Construction of the translation table and editor workspace."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class TranslationWorkspaceWidgets:
    content: QSplitter
    table: QTableView
    source_editor: QPlainTextEdit
    translation_editor: QPlainTextEdit
    model_candidate: QPlainTextEdit
    reviewer_candidate: QPlainTextEdit
    use_model_candidate_button: QPushButton
    use_reviewer_candidate_button: QPushButton
    translation_length: QLabel
    current_issues: QLabel
    dismiss_ai_issue_button: QPushButton
    retranslate_button: QPushButton
    apply_matching_button: QPushButton
    copy_source_button: QPushButton
    apply_button: QPushButton
    approve_button: QPushButton
    lock_button: QPushButton
    model_name: QLabel
    translate_button: QPushButton
    cancel_button: QPushButton
    progress: QProgressBar


def build_translation_workspace_widgets(
    parent: QWidget,
    *,
    table_model: QAbstractItemModel,
    add_filters: Callable[[QHBoxLayout], None],
    current_row_changed: Callable[[QModelIndex, QModelIndex], None],
    select_candidate: Callable[[str], None],
    refresh_translation_length: Callable[[], None],
    dismiss_ai_issue: Callable[[], None],
    retranslate_current: Callable[[], None],
    apply_to_matches: Callable[[], None],
    copy_source: Callable[[], None],
    apply_translation: Callable[[], object],
    toggle_approval: Callable[[], None],
    set_locked: Callable[[bool], None],
    translate_selected: Callable[[], None],
    cancel_translation: Callable[[], None],
) -> TranslationWorkspaceWidgets:
    """Create the translation table, editor and entry-level controls."""
    table = QTableView(parent)
    table.setModel(table_model)
    table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
    table.horizontalHeader().setStretchLastSection(True)
    table.setSortingEnabled(True)
    table.selectionModel().currentRowChanged.connect(current_row_changed)
    filter_layout = QHBoxLayout()
    add_filters(filter_layout)
    table_widget = QWidget(parent)
    table_layout = QVBoxLayout(table_widget)
    table_layout.addLayout(filter_layout)
    table_layout.addWidget(table)

    source_editor = QPlainTextEdit(parent)
    source_editor.setReadOnly(True)
    translation_editor = QPlainTextEdit(parent)
    translation_editor.textChanged.connect(refresh_translation_length)
    model_candidate = QPlainTextEdit(parent)
    model_candidate.setReadOnly(True)
    model_candidate.setPlaceholderText("No translation-model version")
    reviewer_candidate = QPlainTextEdit(parent)
    reviewer_candidate.setReadOnly(True)
    reviewer_candidate.setPlaceholderText("No reviewer suggestion")

    use_model_button = QPushButton("Use model version", parent)
    use_model_button.setToolTip(
        "Make the translation model's version the active translation"
    )
    use_model_button.clicked.connect(lambda: select_candidate("model"))
    use_reviewer_button = QPushButton("Use reviewer version", parent)
    use_reviewer_button.setToolTip(
        "Make the reviewer's corrected version the active translation"
    )
    use_reviewer_button.clicked.connect(lambda: select_candidate("reviewer"))
    translation_length = QLabel("Characters: 0", parent)
    current_issues = QLabel("No validation issues", parent)
    current_issues.setWordWrap(True)
    current_issues.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
    )

    dismiss_button = QPushButton("Dismiss AI issue", parent)
    dismiss_button.setToolTip("Dismiss the AI reviewer issue for the current entry")
    dismiss_button.clicked.connect(dismiss_ai_issue)
    retranslate_button = QPushButton("Re-translate", parent)
    retranslate_button.setToolTip("Translate the current entry again with Ollama")
    retranslate_button.clicked.connect(retranslate_current)
    apply_matching_button = QPushButton("Apply to matching source", parent)
    apply_matching_button.setToolTip(
        "Apply this translation to every unlocked entry with identical source text"
    )
    apply_matching_button.clicked.connect(apply_to_matches)
    copy_source_button = QPushButton("Copy source", parent)
    copy_source_button.setToolTip("Copy the source text into the translation editor")
    copy_source_button.clicked.connect(copy_source)
    apply_button = QPushButton("Apply translation", parent)
    apply_button.clicked.connect(apply_translation)
    apply_button.setToolTip("Save the edited translation (Ctrl+Enter)")
    approve_button = QPushButton("Approve", parent)
    approve_button.setToolTip("Approve or reopen the current translation")
    approve_button.clicked.connect(toggle_approval)
    lock_button = QPushButton("Locked", parent)
    lock_button.setToolTip("Prevent or allow changes to the current translation")
    lock_button.setCheckable(True)
    lock_button.clicked.connect(set_locked)
    model_name = QLabel("qwen3", parent)
    translate_button = QPushButton("Translate selected", parent)
    translate_button.setToolTip("Translate the selected unlocked entries")
    translate_button.clicked.connect(translate_selected)
    cancel_button = QPushButton("Cancel", parent)
    cancel_button.setToolTip("Cancel the operation after the current model request")
    cancel_button.clicked.connect(cancel_translation)
    cancel_button.setVisible(False)
    progress = QProgressBar(parent)
    progress.setRange(0, 1)
    progress.setVisible(False)

    editor_widget = QWidget(parent)
    editor_layout = QVBoxLayout(editor_widget)
    form_layout = QFormLayout()
    form_layout.addRow(QLabel("Source", parent), source_editor)
    form_layout.addRow(QLabel("Translation", parent), translation_editor)
    form_layout.addRow(QLabel("Length", parent), translation_length)
    editor_layout.addLayout(form_layout)
    candidates_layout = QHBoxLayout()
    model_layout = QVBoxLayout()
    model_layout.addWidget(QLabel("Translation model version", parent))
    model_layout.addWidget(model_candidate)
    model_layout.addWidget(use_model_button)
    reviewer_layout = QVBoxLayout()
    reviewer_layout.addWidget(QLabel("Reviewer version", parent))
    reviewer_layout.addWidget(reviewer_candidate)
    reviewer_layout.addWidget(use_reviewer_button)
    candidates_layout.addLayout(model_layout)
    candidates_layout.addLayout(reviewer_layout)
    editor_layout.addLayout(candidates_layout)
    editor_layout.addWidget(current_issues)
    for buttons in (
        (dismiss_button, retranslate_button, apply_matching_button),
        (copy_source_button, apply_button),
        (approve_button, lock_button),
    ):
        row = QHBoxLayout()
        for button in buttons:
            row.addWidget(button)
        editor_layout.addLayout(row)
    translation_controls = QHBoxLayout()
    translation_controls.addWidget(QLabel("Model", parent))
    translation_controls.addWidget(model_name)
    translation_controls.addWidget(translate_button)
    translation_controls.addWidget(cancel_button)
    editor_layout.addLayout(translation_controls)
    editor_layout.addWidget(progress)

    content = QSplitter(Qt.Orientation.Horizontal, parent)
    content.addWidget(table_widget)
    content.addWidget(editor_widget)
    content.setStretchFactor(0, 3)
    content.setStretchFactor(1, 2)
    return TranslationWorkspaceWidgets(
        content,
        table,
        source_editor,
        translation_editor,
        model_candidate,
        reviewer_candidate,
        use_model_button,
        use_reviewer_button,
        translation_length,
        current_issues,
        dismiss_button,
        retranslate_button,
        apply_matching_button,
        copy_source_button,
        apply_button,
        approve_button,
        lock_button,
        model_name,
        translate_button,
        cancel_button,
        progress,
    )
