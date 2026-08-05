"""Main PySide6 window for the desktop MVP."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QModelIndex, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from locaforge.application.dto.review import ReviewBatchResult
from locaforge.application.dto.translation import BatchResult
from locaforge.application.dto.validation import (
    EntryValidationIssue,
    ProjectValidationResult,
    ValidationCode,
)
from locaforge.application.ports.csv_format import CsvFieldMapping
from locaforge.application.ports.json_format import JsonFieldMapping
from locaforge.application.ports.xml_format import XmlFieldMapping
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.glossary import GlossaryTerm
from locaforge.domain.translation_memory import TranslationMemoryMatch
from locaforge.presentation.autosave_controller import AutosaveController
from locaforge.presentation.batch_translation_worker import BatchTranslationWorker
from locaforge.presentation.json_import_profiles import (
    JsonImportProfile,
    JsonImportProfileStore,
)
from locaforge.presentation.log_viewer import LogViewerController
from locaforge.presentation.ollama_settings_dialog import OllamaSettingsDialog
from locaforge.presentation.recent_projects import RecentProjectsStore
from locaforge.presentation.review_worker import ReviewWorker
from locaforge.presentation.translation_filter_proxy import TranslationFilterProxyModel
from locaforge.presentation.translation_length import format_translation_length
from locaforge.presentation.translation_memory_worker import TranslationMemoryWorker
from locaforge.presentation.translation_navigation import (
    adjacent_row_index,
    next_matching_entry_id,
)
from locaforge.presentation.translation_table_model import TranslationTableModel
from locaforge.presentation.validation_filter import (
    filter_validation_issues,
    format_validation_issues,
    group_attention_issues,
)
from locaforge.presentation.validation_worker import ValidationWorker
from locaforge.presentation.window_layout import WindowLayoutStore

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        workspace: ProjectWorkspace,
        layout_store: WindowLayoutStore | None = None,
        recent_projects: RecentProjectsStore | None = None,
    ) -> None:
        super().__init__()
        self._workspace = workspace
        self._layout_store = layout_store or WindowLayoutStore(QSettings())
        self._recent_projects = recent_projects or RecentProjectsStore(QSettings())
        self._json_import_profiles = JsonImportProfileStore(QSettings())
        self._model = TranslationTableModel(self)
        self._proxy_model = TranslationFilterProxyModel()
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.modelReset.connect(self._refresh_filter_result_count)
        self._proxy_model.rowsInserted.connect(self._refresh_filter_result_count)
        self._proxy_model.rowsRemoved.connect(self._refresh_filter_result_count)
        self._current_entry_id: str | None = None
        self._current_entry_locked = False
        self._current_entry_max_length: int | None = None
        self._validation_issues_by_entry: dict[str, tuple[EntryValidationIssue, ...]] = {}
        self._translation_memory_suggestion: str | None = None
        self._translation_worker: BatchTranslationWorker | None = None
        self._review_worker: ReviewWorker | None = None
        self._translation_memory_worker: TranslationMemoryWorker | None = None
        self._validation_worker: ValidationWorker | None = None
        self._translation_memory_cache: dict[
            str, tuple[TranslationMemoryMatch, ...]
        ] = {}
        self._memory_request_id = 0
        self._pending_memory_entry_id: str | None = None
        self._memory_lookup_timer = QTimer(self)
        self._memory_lookup_timer.setSingleShot(True)
        self._memory_lookup_timer.setInterval(120)
        self._memory_lookup_timer.timeout.connect(
            self._start_pending_translation_memory_lookup
        )
        self._busy = False

        self._table = QTableView(self)
        self._table.setModel(self._proxy_model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSortingEnabled(True)
        self._table.selectionModel().currentRowChanged.connect(self._on_current_row_changed)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText(
            "Search key, source, translation, or context (Ctrl+F)"
        )
        self._search.textChanged.connect(self._set_search_filter)
        self._search_filter_timer = QTimer(self)
        self._search_filter_timer.setSingleShot(True)
        self._search_filter_timer.setInterval(150)
        self._search_filter_timer.timeout.connect(self._apply_search_filter)
        self._status_filter = QToolButton(self)
        self._status_filter.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._status_filter_menu = QMenu(self)
        self._status_filter.setMenu(self._status_filter_menu)
        self._status_filter_actions: dict[str, QAction] = {}
        self._status_filter_labels: dict[str, str] = {}
        self._status_filter_timer = QTimer(self)
        self._status_filter_timer.setSingleShot(True)
        self._status_filter_timer.setInterval(180)
        self._status_filter_timer.timeout.connect(self._apply_status_filter)
        self._summary_refresh_timer = QTimer(self)
        self._summary_refresh_timer.setSingleShot(True)
        self._summary_refresh_timer.setInterval(500)
        self._summary_refresh_timer.timeout.connect(self._refresh_project_sidebars)
        for label, status in (
            ("Untranslated", "untranslated"),
            ("Translated", "translated"),
            ("Needs review", "needs_review"),
            ("Approved", "approved"),
            ("Error", "error"),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            action.toggled.connect(
                lambda checked, selected_status=status: self._set_status_filter(
                    selected_status, checked
                )
            )
            self._status_filter_menu.addAction(action)
            self._status_filter_actions[status] = action
            self._status_filter_labels[status] = label
        self._update_status_filter_label()
        self._issues_only_filter = QToolButton(self)
        self._issues_only_filter.setCheckable(True)
        self._issues_only_filter.setToolTip("Show only entries with validation issues")
        self._issues_only_filter.toggled.connect(self._apply_issue_filter)
        self._update_issue_filter_label()
        self._clear_filters_button = QToolButton(self)
        self._clear_filters_button.setText("Clear filters")
        self._clear_filters_button.setToolTip("Clear table filters (Ctrl+Shift+F)")
        self._clear_filters_button.clicked.connect(self._clear_filters)
        self._filter_result_count = QLabel("0 / 0 entries", self)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(self._search)
        filter_layout.addWidget(self._status_filter)
        filter_layout.addWidget(self._issues_only_filter)
        filter_layout.addWidget(self._clear_filters_button)
        filter_layout.addWidget(self._filter_result_count)
        table_widget = QWidget(self)
        table_layout = QVBoxLayout(table_widget)
        table_layout.addLayout(filter_layout)
        table_layout.addWidget(self._table)

        self._source_editor = QPlainTextEdit(self)
        self._source_editor.setReadOnly(True)
        self._translation_editor = QPlainTextEdit(self)
        self._translation_length = QLabel("Characters: 0", self)
        self._translation_editor.textChanged.connect(self._refresh_translation_length)
        self._current_issues = QLabel("No validation issues", self)
        self._current_issues.setWordWrap(True)
        self._current_issues.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._dismiss_ai_issue_button = QPushButton("Dismiss AI issue", self)
        self._dismiss_ai_issue_button.clicked.connect(self._dismiss_ai_review_issue)
        self._retranslate_button = QPushButton("Re-translate", self)
        self._retranslate_button.clicked.connect(self._retranslate_current_entry)
        self._apply_matching_button = QPushButton(
            "Apply to matching source", self
        )
        self._apply_matching_button.clicked.connect(self._apply_translation_to_matches)
        self._copy_source_button = QPushButton("Copy source", self)
        self._copy_source_button.clicked.connect(self._copy_source_to_translation)
        self._apply_button = QPushButton("Apply translation", self)
        self._apply_button.clicked.connect(self._apply_translation)
        self._apply_button.setToolTip("Ctrl+Enter")
        self._approve_button = QPushButton("Approve", self)
        self._approve_button.clicked.connect(self._toggle_entry_approval)
        self._lock_button = QPushButton("Locked", self)
        self._lock_button.setCheckable(True)
        self._lock_button.clicked.connect(self._set_entry_locked)
        self._model_name = QLabel("qwen3", self)
        self._settings_button = QPushButton("Settings...", self)
        self._settings_button.clicked.connect(self._open_ollama_settings)
        self._translate_button = QPushButton("Translate selected", self)
        self._translate_button.clicked.connect(self._translate_selected)
        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.clicked.connect(self._cancel_translation)
        self._cancel_button.setVisible(False)
        self._progress = QProgressBar(self)
        self._progress.setRange(0, 1)
        self._progress.setVisible(False)

        editor_widget = QWidget(self)
        editor_layout = QVBoxLayout(editor_widget)
        form_layout = QFormLayout()
        form_layout.addRow(QLabel("Source", self), self._source_editor)
        form_layout.addRow(QLabel("Translation", self), self._translation_editor)
        form_layout.addRow(QLabel("Length", self), self._translation_length)
        editor_layout.addLayout(form_layout)
        editor_layout.addWidget(self._current_issues)
        issue_actions = QHBoxLayout()
        issue_actions.addWidget(self._dismiss_ai_issue_button)
        issue_actions.addWidget(self._retranslate_button)
        issue_actions.addWidget(self._apply_matching_button)
        editor_layout.addLayout(issue_actions)
        manual_actions = QHBoxLayout()
        manual_actions.addWidget(self._copy_source_button)
        manual_actions.addWidget(self._apply_button)
        editor_layout.addLayout(manual_actions)
        review_controls = QHBoxLayout()
        review_controls.addWidget(self._approve_button)
        review_controls.addWidget(self._lock_button)
        editor_layout.addLayout(review_controls)
        translation_controls = QHBoxLayout()
        translation_controls.addWidget(QLabel("Ollama model", self))
        translation_controls.addWidget(self._model_name)
        translation_controls.addWidget(self._settings_button)
        translation_controls.addWidget(self._translate_button)
        translation_controls.addWidget(self._cancel_button)
        editor_layout.addLayout(translation_controls)
        editor_layout.addWidget(self._progress)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(table_widget)
        splitter.addWidget(editor_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

        self._project_explorer = QListWidget(self)
        self._project_explorer.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        project_dock = QDockWidget("Project Explorer", self)
        project_dock.setObjectName("project_explorer_dock")
        project_dock.setWidget(self._project_explorer)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, project_dock)

        self._validation_list = QListWidget(self)
        self._validation_list.itemActivated.connect(self._activate_validation_issue)
        self._validation_filter = QComboBox(self)
        self._validation_filter.addItem("All issues", None)
        self._validation_filter.addItem("Requires attention", "attention")
        self._validation_filter.addItem("AI Reviewer", "ai_review")
        self._validation_filter.addItem("Consistency", "consistency")
        self._validation_filter.addItem("Structural", "structural")
        self._validation_filter.currentIndexChanged.connect(
            self._refresh_validation_issues
        )
        validation_widget = QWidget(self)
        validation_layout = QVBoxLayout(validation_widget)
        validation_layout.addWidget(self._validation_filter)
        validation_layout.addWidget(self._validation_list)
        validation_dock = QDockWidget("Validation", self)
        validation_dock.setObjectName("validation_dock")
        validation_dock.setWidget(validation_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, validation_dock)

        self._history_list = QListWidget(self)
        self._history_list.currentItemChanged.connect(self._on_history_selection_changed)
        self._history_list.itemActivated.connect(self._activate_history_revision)
        self._restore_history_button = QPushButton("Restore revision", self)
        self._restore_history_button.clicked.connect(self._restore_history_revision)
        history_widget = QWidget(self)
        history_layout = QVBoxLayout(history_widget)
        history_layout.addWidget(self._history_list)
        history_layout.addWidget(self._restore_history_button)
        history_dock = QDockWidget("History", self)
        history_dock.setObjectName("history_dock")
        history_dock.setWidget(history_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, history_dock)
        self.tabifyDockWidget(validation_dock, history_dock)
        validation_dock.raise_()

        self._log_view = QPlainTextEdit(self)
        self._log_view.setReadOnly(True)
        self._log_view.document().setMaximumBlockCount(1_000)
        self._clear_log_button = QPushButton("Clear logs", self)
        self._clear_log_button.clicked.connect(self._log_view.clear)
        log_widget = QWidget(self)
        log_layout = QVBoxLayout(log_widget)
        log_layout.addWidget(self._log_view)
        log_layout.addWidget(self._clear_log_button)
        logs_dock = QDockWidget("Logs", self)
        logs_dock.setObjectName("logs_dock")
        logs_dock.setWidget(log_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, logs_dock)
        self.tabifyDockWidget(history_dock, logs_dock)

        self._translation_memory_list = QListWidget(self)
        self._translation_memory_list.currentItemChanged.connect(
            self._select_memory_suggestion
        )
        self._translation_memory_list.itemActivated.connect(
            self._activate_memory_suggestion
        )
        self._apply_memory_button = QPushButton("Apply TM suggestion", self)
        self._apply_memory_button.clicked.connect(self._apply_memory_suggestion)
        memory_widget = QWidget(self)
        memory_layout = QVBoxLayout(memory_widget)
        memory_layout.addWidget(self._translation_memory_list)
        memory_layout.addWidget(self._apply_memory_button)
        memory_dock = QDockWidget("Translation Memory", self)
        memory_dock.setObjectName("translation_memory_dock")
        memory_dock.setWidget(memory_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, memory_dock)

        self._glossary_list = QListWidget(self)
        self._glossary_list.currentItemChanged.connect(self._on_glossary_selection_changed)
        self._glossary_add_button = QPushButton("Add term...", self)
        self._glossary_add_button.clicked.connect(self._add_glossary_term)
        self._glossary_remove_button = QPushButton("Remove term", self)
        self._glossary_remove_button.clicked.connect(self._remove_glossary_term)
        self._glossary_import_button = QPushButton("Import CSV...", self)
        self._glossary_import_button.clicked.connect(self._import_glossary_csv)
        self._glossary_export_button = QPushButton("Export CSV...", self)
        self._glossary_export_button.clicked.connect(self._export_glossary_csv)
        glossary_buttons = QHBoxLayout()
        glossary_buttons.addWidget(self._glossary_add_button)
        glossary_buttons.addWidget(self._glossary_remove_button)
        glossary_buttons.addWidget(self._glossary_import_button)
        glossary_buttons.addWidget(self._glossary_export_button)
        glossary_widget = QWidget(self)
        glossary_layout = QVBoxLayout(glossary_widget)
        glossary_layout.addWidget(self._glossary_list)
        glossary_layout.addLayout(glossary_buttons)
        glossary_dock = QDockWidget("Glossary", self)
        glossary_dock.setObjectName("glossary_dock")
        glossary_dock.setWidget(glossary_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, glossary_dock)
        self.tabifyDockWidget(memory_dock, glossary_dock)
        memory_dock.raise_()

        self._save_action = QAction("&Save", self)
        self._save_action.triggered.connect(self._save_project)
        self._save_as_action = QAction("Save &As...", self)
        self._save_as_action.triggered.connect(self._save_project_as)
        self._export_action = QAction("&Export JSON...", self)
        self._export_action.triggered.connect(self._export_json)
        self._export_po_action = QAction("Export &PO...", self)
        self._export_po_action.triggered.connect(self._export_po)
        self._export_csv_action = QAction("Export &CSV/TSV...", self)
        self._export_csv_action.triggered.connect(self._export_csv)
        self._export_xml_action = QAction("Export &XML...", self)
        self._export_xml_action.triggered.connect(self._export_xml)
        self._build_menu()

        self._autosave = AutosaveController(self._workspace.autosave, parent=self)
        self._autosave.saved.connect(self._autosave_succeeded)
        self._autosave.failed.connect(self._autosave_failed)
        self._log_viewer = LogViewerController(parent=self)
        self._log_viewer.message_logged.connect(self._log_view.appendPlainText)
        self._log_viewer.attach()
        logger.info("Log viewer attached")

        self.resize(1200, 720)
        self._default_window_geometry = self.saveGeometry()
        self._default_window_state = self.saveState()
        self._restore_window_layout()
        self.statusBar().showMessage("Ready")
        self._refresh_project()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        self._import_action = QAction("&Import JSON...", self)
        self._import_action.triggered.connect(self._import_json)
        self._import_action.setShortcut(QKeySequence("Ctrl+I"))
        self._import_po_action = QAction("Import &PO...", self)
        self._import_po_action.triggered.connect(self._import_po)
        self._import_csv_action = QAction("Import CSV/&TSV...", self)
        self._import_csv_action.triggered.connect(self._import_csv)
        self._import_xml_action = QAction("Import &XML...", self)
        self._import_xml_action.triggered.connect(self._import_xml)
        self._open_action = QAction("&Open project...", self)
        self._open_action.triggered.connect(self._open_project)
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._export_action.setShortcut(QKeySequence("Ctrl+E"))
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)

        file_menu.addAction(self._import_action)
        file_menu.addAction(self._import_po_action)
        file_menu.addAction(self._import_csv_action)
        file_menu.addAction(self._import_xml_action)
        file_menu.addAction(self._open_action)
        self._recent_projects_menu = file_menu.addMenu("Recent projects")
        self._refresh_recent_projects_menu()
        file_menu.addSeparator()
        file_menu.addAction(self._save_action)
        file_menu.addAction(self._save_as_action)
        file_menu.addAction(self._export_action)
        file_menu.addAction(self._export_po_action)
        file_menu.addAction(self._export_csv_action)
        file_menu.addAction(self._export_xml_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        review_menu = self.menuBar().addMenu("&Review")
        self._approve_selected_action = QAction("Approve selected", self)
        self._approve_selected_action.triggered.connect(self._approve_selected)
        self._reopen_selected_action = QAction("Reopen selected", self)
        self._reopen_selected_action.triggered.connect(self._reopen_selected)
        self._lock_selected_action = QAction("Lock selected", self)
        self._lock_selected_action.triggered.connect(self._lock_selected)
        self._unlock_selected_action = QAction("Unlock selected", self)
        self._unlock_selected_action.triggered.connect(self._unlock_selected)
        self._review_selected_action = QAction("AI review selected", self)
        self._review_selected_action.triggered.connect(self._review_selected)
        self._review_all_action = QAction("AI review all Needs review", self)
        self._review_all_action.triggered.connect(self._review_all)
        review_menu.addAction(self._review_selected_action)
        review_menu.addAction(self._review_all_action)
        review_menu.addSeparator()
        review_menu.addAction(self._approve_selected_action)
        review_menu.addAction(self._reopen_selected_action)
        review_menu.addSeparator()
        review_menu.addAction(self._lock_selected_action)
        review_menu.addAction(self._unlock_selected_action)

        tools_menu = self.menuBar().addMenu("&Tools")
        self._translate_all_action = QAction("Translate all untranslated", self)
        self._translate_all_action.triggered.connect(self._translate_all_untranslated)
        self._translate_all_action.setShortcut(QKeySequence("Ctrl+Shift+T"))
        tools_menu.addAction(self._translate_all_action)
        self._replace_translations_action = QAction("Replace translations...", self)
        self._replace_translations_action.triggered.connect(self._replace_translations)
        self._replace_translations_action.setShortcut(QKeySequence("Ctrl+H"))
        tools_menu.addAction(self._replace_translations_action)
        self._validate_project_action = QAction("Validate project", self)
        self._validate_project_action.triggered.connect(self._validate_project)
        self._validate_project_action.setShortcut(QKeySequence("F5"))
        tools_menu.addAction(self._validate_project_action)
        self._apply_translation_action = QAction("Apply current translation", self)
        self._apply_translation_action.triggered.connect(self._apply_translation)
        self._apply_translation_action.setShortcut(QKeySequence("Ctrl+Enter"))
        self.addAction(self._apply_translation_action)
        self._apply_and_next_action = QAction("Apply and select next", self)
        self._apply_and_next_action.triggered.connect(self._apply_and_select_next)
        self._apply_and_next_action.setShortcut(QKeySequence("Ctrl+Shift+Enter"))
        self.addAction(self._apply_and_next_action)
        tools_menu.addSeparator()
        tools_menu.addAction(self._apply_translation_action)
        tools_menu.addAction(self._apply_and_next_action)

        navigate_menu = self.menuBar().addMenu("&Navigate")
        self._previous_entry_action = QAction("Previous entry", self)
        self._previous_entry_action.triggered.connect(
            lambda: self._select_relative_entry(-1)
        )
        self._previous_entry_action.setShortcut(QKeySequence("Ctrl+Alt+Up"))
        self.addAction(self._previous_entry_action)
        self._next_entry_action = QAction("Next entry", self)
        self._next_entry_action.triggered.connect(lambda: self._select_relative_entry(1))
        self._next_entry_action.setShortcut(QKeySequence("Ctrl+Alt+Down"))
        self.addAction(self._next_entry_action)
        self._previous_issue_action = QAction("Previous issue", self)
        self._previous_issue_action.triggered.connect(
            lambda: self._select_relative_issue(-1)
        )
        self._previous_issue_action.setShortcut(QKeySequence("Shift+F6"))
        self.addAction(self._previous_issue_action)
        self._next_issue_action = QAction("Next issue", self)
        self._next_issue_action.triggered.connect(lambda: self._select_relative_issue(1))
        self._next_issue_action.setShortcut(QKeySequence("F6"))
        self.addAction(self._next_issue_action)
        self._next_actionable_entry_action = QAction("Next actionable entry", self)
        self._next_actionable_entry_action.triggered.connect(
            self._select_next_actionable_entry
        )
        self._next_actionable_entry_action.setShortcut(QKeySequence("F7"))
        self.addAction(self._next_actionable_entry_action)
        self._focus_search_action = QAction("Focus search", self)
        self._focus_search_action.triggered.connect(self._focus_search)
        self._focus_search_action.setShortcut(QKeySequence.StandardKey.Find)
        self.addAction(self._focus_search_action)
        self._clear_filters_action = QAction("Clear table filters", self)
        self._clear_filters_action.triggered.connect(self._clear_filters)
        self._clear_filters_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.addAction(self._clear_filters_action)
        navigate_menu.addAction(self._previous_entry_action)
        navigate_menu.addAction(self._next_entry_action)
        navigate_menu.addSeparator()
        navigate_menu.addAction(self._previous_issue_action)
        navigate_menu.addAction(self._next_issue_action)
        navigate_menu.addAction(self._next_actionable_entry_action)
        navigate_menu.addSeparator()
        navigate_menu.addAction(self._focus_search_action)
        navigate_menu.addAction(self._clear_filters_action)

        view_menu = self.menuBar().addMenu("&View")
        self._reset_layout_action = QAction("Reset layout", self)
        self._reset_layout_action.triggered.connect(self._reset_window_layout)
        view_menu.addAction(self._reset_layout_action)

    def _import_json(self) -> None:
        source_name, _ = QFileDialog.getOpenFileName(
            self, "Import JSON", "", "JSON files (*.json)"
        )
        if not source_name:
            return
        field_mapping = self._ask_json_field_mapping(Path(source_name))
        destination_name, _ = QFileDialog.getSaveFileName(
            self, "Create LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        if not destination_name:
            return
        source_language = self._ask_language("Source language", "en")
        if source_language is None:
            return
        target_language = self._ask_language("Target language", "ru")
        if target_language is None:
            return
        if not self._confirm_unsaved_changes():
            return
        destination = Path(destination_name)
        if destination.suffix.lower() != ".lfproj":
            destination = destination.with_suffix(".lfproj")

        if self._run_project_action(
            lambda: self._workspace.create_from_json(
                Path(source_name),
                destination,
                source_language,
                target_language,
                field_mapping,
            ),
            "Project created",
        ):
            self._remember_current_project()

    def _ask_json_field_mapping(self, path: Path) -> JsonFieldMapping | None:
        fields = self._workspace.inspect_json_fields(path)
        if not fields:
            return None
        available_profiles = tuple(
            profile
            for profile in self._json_import_profiles.list_profiles()
            if profile.mapping.source_field in fields
            and profile.mapping.target_field in fields
            and (profile.mapping.key_field is None or profile.mapping.key_field in fields)
        )
        if available_profiles:
            profile_names = (
                "<configure fields>",
                *(profile.name for profile in available_profiles),
            )
            selected_name, accepted = QInputDialog.getItem(
                self, "JSON import profile", "Use import profile:", profile_names, 0, False
            )
            if not accepted:
                return None
            if selected_name != "<configure fields>":
                return next(
                    profile.mapping
                    for profile in available_profiles
                    if profile.name == selected_name
                )
        if QMessageBox.question(
            self,
            "JSON import fields",
            "Detected object fields:\n"
            f"{', '.join(fields)}\n\nSelect only localization fields?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        ) != QMessageBox.StandardButton.Yes:
            return None
        source_field, accepted = QInputDialog.getItem(
            self, "JSON import fields", "Source text field:", fields, 0, False
        )
        if not accepted:
            return None
        target_field, accepted = QInputDialog.getItem(
            self, "JSON import fields", "Translation field:", fields, 0, False
        )
        if not accepted or target_field == source_field:
            return None
        key_options = ("<generated path>", *fields)
        key_field, accepted = QInputDialog.getItem(
            self, "JSON import fields", "Key field:", key_options, 0, False
        )
        if not accepted:
            return None
        mapping = JsonFieldMapping(
            source_field,
            target_field,
            None if key_field == "<generated path>" else key_field,
            QMessageBox.question(
                self,
                "Existing translations",
                "Import existing target-field values as translations needing review?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            == QMessageBox.StandardButton.Yes,
        )
        if QMessageBox.question(
            self,
            "JSON import profile",
            "Save this field mapping as a reusable profile?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            profile_name, accepted = QInputDialog.getText(
                self, "JSON import profile", "Profile name:"
            )
            if accepted and profile_name.strip():
                self._json_import_profiles.save(
                    JsonImportProfile(profile_name.strip(), mapping)
                )
        return mapping

    def _import_po(self) -> None:
        source_name, _ = QFileDialog.getOpenFileName(
            self, "Import PO", "", "Gettext PO files (*.po)"
        )
        if not source_name:
            return
        destination_name, _ = QFileDialog.getSaveFileName(
            self, "Create LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        if not destination_name:
            return
        source_language = self._ask_language("Source language", "en")
        if source_language is None:
            return
        target_language = self._ask_language("Target language", "ru")
        if target_language is None or not self._confirm_unsaved_changes():
            return
        destination = Path(destination_name)
        if destination.suffix.lower() != ".lfproj":
            destination = destination.with_suffix(".lfproj")
        if self._run_project_action(
            lambda: self._workspace.create_from_po(
                Path(source_name),
                destination,
                source_language,
                target_language,
            ),
            "Project created",
        ):
            self._remember_current_project()

    def _import_csv(self) -> None:
        source_name, _ = QFileDialog.getOpenFileName(
            self,
            "Import CSV/TSV",
            "",
            "Delimited text files (*.csv *.tsv);;All files (*)",
        )
        if not source_name:
            return
        source_path = Path(source_name)
        field_mapping = self._ask_csv_field_mapping(source_path)
        if field_mapping is None:
            return
        destination_name, _ = QFileDialog.getSaveFileName(
            self, "Create LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        if not destination_name:
            return
        source_language = self._ask_language("Source language", "en")
        if source_language is None:
            return
        target_language = self._ask_language("Target language", "ru")
        if target_language is None or not self._confirm_unsaved_changes():
            return
        destination = Path(destination_name)
        if destination.suffix.lower() != ".lfproj":
            destination = destination.with_suffix(".lfproj")
        if self._run_project_action(
            lambda: self._workspace.create_from_csv(
                source_path,
                destination,
                source_language,
                target_language,
                field_mapping,
            ),
            "Project created",
        ):
            self._remember_current_project()

    def _import_xml(self) -> None:
        source_name, _ = QFileDialog.getOpenFileName(
            self, "Import XML", "", "XML files (*.xml)"
        )
        if not source_name:
            return
        field_mapping = self._ask_xml_field_mapping(Path(source_name))
        destination_name, _ = QFileDialog.getSaveFileName(
            self, "Create LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        if not destination_name:
            return
        source_language = self._ask_language("Source language", "en")
        if source_language is None:
            return
        target_language = self._ask_language("Target language", "ru")
        if target_language is None or not self._confirm_unsaved_changes():
            return
        destination = Path(destination_name)
        if destination.suffix.lower() != ".lfproj":
            destination = destination.with_suffix(".lfproj")
        if self._run_project_action(
            lambda: self._workspace.create_from_xml(
                Path(source_name),
                destination,
                source_language,
                target_language,
                field_mapping,
            ),
            "Project created",
        ):
            self._remember_current_project()

    def _ask_xml_field_mapping(self, path: Path) -> XmlFieldMapping | None:
        attribute_names = self._workspace.inspect_xml_attribute_names(path)
        if not attribute_names:
            return None
        if QMessageBox.question(
            self,
            "XML attributes",
            "Also import text from selected XML attributes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return None
        selected_names, accepted = QInputDialog.getText(
            self,
            "XML attributes",
            "Attribute names (comma-separated):\n"
            f"Available: {', '.join(attribute_names)}",
        )
        if not accepted or not selected_names.strip():
            return None
        selected = tuple(
            name.strip() for name in selected_names.split(",") if name.strip()
        )
        unknown_names = sorted(set(selected).difference(attribute_names))
        if unknown_names:
            QMessageBox.warning(
                self,
                "XML attributes",
                f"Unknown attribute names: {', '.join(unknown_names)}",
            )
            return None
        return XmlFieldMapping(selected)

    def _ask_csv_field_mapping(self, path: Path) -> CsvFieldMapping | None:
        fields = self._workspace.inspect_csv_fields(path)
        source_field, accepted = QInputDialog.getItem(
            self, "CSV import fields", "Source text field:", fields, 0, False
        )
        if not accepted:
            return None
        target_field, accepted = QInputDialog.getItem(
            self, "CSV import fields", "Translation field:", fields, 0, False
        )
        if not accepted or target_field == source_field:
            return None
        key_options = ("<generated row>", *fields)
        key_field, accepted = QInputDialog.getItem(
            self, "CSV import fields", "Key field:", key_options, 0, False
        )
        if not accepted:
            return None
        import_existing = (
            QMessageBox.question(
                self,
                "Existing translations",
                "Import existing target-column values as translations needing review?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            == QMessageBox.StandardButton.Yes
        )
        return CsvFieldMapping(
            source_field,
            target_field,
            None if key_field == "<generated row>" else key_field,
            import_existing,
        )

    def _open_project(self) -> None:
        path_name, _ = QFileDialog.getOpenFileName(
            self, "Open LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        if path_name:
            if not self._confirm_unsaved_changes():
                return
            if self._run_project_action(
                lambda: self._workspace.open(Path(path_name)), "Project opened"
            ):
                self._remember_current_project()

    def _save_project(self) -> None:
        if self._run_project_action(self._workspace.save, "Project saved"):
            self._remember_current_project()

    def _save_project_as(self) -> None:
        if not self._workspace.has_project:
            return
        path_name, _ = QFileDialog.getSaveFileName(
            self, "Save LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        if not path_name:
            return
        destination = Path(path_name)
        if destination.suffix.lower() != ".lfproj":
            destination = destination.with_suffix(".lfproj")
        if self._run_project_action(
            lambda: self._workspace.save(destination), "Project saved"
        ):
            self._remember_current_project()

    def _export_json(self) -> None:
        if not self._workspace.has_project:
            return
        if not self._confirm_export_warnings("will retain source text"):
            return
        path_name, _ = QFileDialog.getSaveFileName(
            self, "Export translated JSON", "", "JSON files (*.json)"
        )
        if not path_name:
            return
        destination = Path(path_name)
        if destination.suffix.lower() != ".json":
            destination = destination.with_suffix(".json")
        self._run_project_action(
            lambda: self._workspace.export_json(destination), "JSON exported"
        )

    def _export_po(self) -> None:
        if not self._workspace.has_project or not self._confirm_export_warnings(
            "will be empty"
        ):
            return
        path_name, _ = QFileDialog.getSaveFileName(
            self, "Export translated PO", "", "Gettext PO files (*.po)"
        )
        if not path_name:
            return
        destination = Path(path_name)
        if destination.suffix.lower() != ".po":
            destination = destination.with_suffix(".po")
        self._run_project_action(
            lambda: self._workspace.export_po(destination), "PO exported"
        )

    def _export_csv(self) -> None:
        if not self._workspace.has_project or not self._confirm_export_warnings(
            "will be empty"
        ):
            return
        path_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export translated CSV/TSV",
            "",
            "Delimited text files (*.csv *.tsv)",
        )
        if not path_name:
            return
        destination = Path(path_name)
        if destination.suffix.lower() not in {".csv", ".tsv"}:
            destination = destination.with_suffix(".csv")
        self._run_project_action(
            lambda: self._workspace.export_csv(destination), "CSV/TSV exported"
        )

    def _export_xml(self) -> None:
        if not self._workspace.has_project or not self._confirm_export_warnings(
            "will retain source text"
        ):
            return
        path_name, _ = QFileDialog.getSaveFileName(
            self, "Export translated XML", "", "XML files (*.xml)"
        )
        if not path_name:
            return
        destination = Path(path_name)
        if destination.suffix.lower() != ".xml":
            destination = destination.with_suffix(".xml")
        self._run_project_action(
            lambda: self._workspace.export_xml(destination), "XML exported"
        )

    def _confirm_export_warnings(self, untranslated_effect: str) -> bool:
        preflight = self._workspace.export_preflight()
        if not preflight.has_warnings:
            return True
        warning_parts: list[str] = []
        if preflight.untranslated_entries:
            warning_parts.append(
                f"{preflight.untranslated_entries} untranslated entries "
                f"{untranslated_effect}"
            )
        if preflight.entries_with_issues:
            warning_parts.append(
                f"{preflight.entries_with_issues} entries have validation issues"
            )
        return (
            QMessageBox.question(
                self,
                "Export warnings",
                ".\n".join(warning_parts) + ".\n\nExport anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            == QMessageBox.StandardButton.Yes
        )

    def _apply_translation(self) -> bool:
        if self._current_entry_id is None:
            return False
        translation = self._translation_editor.toPlainText()
        return self._run_entry_action(
            lambda: self._workspace.edit_translation(
                self._current_entry_id or "", translation
            ),
            "Translation updated",
        )

    def _copy_source_to_translation(self) -> None:
        if self._current_entry_id is None or self._current_entry_locked or self._busy:
            return
        self._translation_editor.setPlainText(self._source_editor.toPlainText())
        self.statusBar().showMessage("Source copied to translation editor", 3000)

    def _apply_and_select_next(self) -> None:
        if self._apply_translation():
            self._select_relative_entry(1)

    def _select_relative_entry(self, offset: int) -> None:
        current_index = self._table.currentIndex()
        current_row = current_index.row() if current_index.isValid() else 0
        target_row = adjacent_row_index(
            current_row, self._proxy_model.rowCount(), offset
        )
        if target_row is None:
            return
        target_index = self._proxy_model.index(target_row, 0)
        self._table.selectRow(target_row)
        self._table.scrollTo(target_index)

    def _select_relative_issue(self, offset: int) -> None:
        if not self._workspace.has_project or self._busy:
            return
        entry_id = next_matching_entry_id(
            tuple(entry.id for entry in self._workspace.project.entries),
            self._current_entry_id,
            self._validation_issues_by_entry,
            offset,
        )
        if entry_id is None:
            self.statusBar().showMessage("No validation issues", 3000)
            return
        self._select_entry_by_id(entry_id)

    def _select_next_actionable_entry(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        actionable_statuses = {
            EntryStatus.UNTRANSLATED,
            EntryStatus.NEEDS_REVIEW,
            EntryStatus.ERROR,
        }
        entry_ids = tuple(entry.id for entry in self._workspace.project.entries)
        actionable_entry_ids = {
            entry.id
            for entry in self._workspace.project.entries
            if not entry.locked and entry.status in actionable_statuses
        }
        entry_id = next_matching_entry_id(
            entry_ids, self._current_entry_id, actionable_entry_ids, 1
        )
        if entry_id is None:
            self.statusBar().showMessage("No actionable entries", 3000)
            return
        self._issues_only_filter.setChecked(False)
        self._select_entry_by_id(entry_id)

    def _apply_translation_to_matches(self) -> None:
        if self._current_entry_id is None:
            return
        translation = self._translation_editor.toPlainText()
        if not translation.strip():
            QMessageBox.warning(
                self,
                "Apply to matching source",
                "Enter a non-empty translation before applying it to matching entries.",
            )
            return
        current_entry = self._workspace.project.get_entry(self._current_entry_id)
        matching_count = sum(
            not entry.locked
            and entry.source == current_entry.source
            and entry.context == current_entry.context
            for entry in self._workspace.project.entries
        )
        if matching_count < 2:
            return
        if QMessageBox.question(
            self,
            "Apply to matching source",
            f"Apply this translation to {matching_count} matching unlocked entries?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._run_project_action(
            lambda: self._workspace.apply_translation_to_matches(
                self._current_entry_id or "", translation
            ),
            f"Translation applied to {matching_count} entries",
        )

    def _apply_memory_suggestion(self) -> None:
        if self._translation_memory_suggestion is None:
            return
        self._translation_editor.setPlainText(self._translation_memory_suggestion)
        self._apply_translation()

    def _toggle_entry_approval(self) -> None:
        if self._current_entry_id is None:
            return
        entry = self._workspace.project.get_entry(self._current_entry_id)
        approved = entry.status is not EntryStatus.APPROVED
        self._run_project_action(
            lambda: self._workspace.set_entry_approval(entry.id, approved),
            "Translation approved" if approved else "Translation reopened for review",
        )

    def _set_entry_locked(self, locked: bool) -> None:
        if self._current_entry_id is None:
            self._lock_button.setChecked(False)
            return
        entry_id = self._current_entry_id
        self._run_project_action(
            lambda: self._workspace.set_entry_locked(entry_id, locked),
            "Translation locked" if locked else "Translation unlocked",
        )

    def _restore_history_revision(self) -> None:
        if self._current_entry_id is None:
            return
        item = self._history_list.currentItem()
        revision_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(revision_id, int):
            return
        if QMessageBox.question(
            self,
            "Restore translation revision",
            "Replace the current translation with this previous version?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        entry_id = self._current_entry_id
        self._run_project_action(
            lambda: self._workspace.restore_entry_revision(entry_id, revision_id),
            "Translation revision restored",
        )

    def _add_glossary_term(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        source, accepted = QInputDialog.getText(
            self,
            "Add glossary term",
            "Source term:",
            text=self._source_editor.toPlainText(),
        )
        if not accepted or not source.strip():
            return
        target, accepted = QInputDialog.getText(
            self,
            "Add glossary term",
            "Required translation:",
            text=self._translation_editor.toPlainText(),
        )
        if not accepted or not target.strip():
            return
        case_sensitive = QMessageBox.question(
            self,
            "Glossary term",
            "Match the source term case-sensitively?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes
        self._run_project_action(
            lambda: self._workspace.store_glossary_term(
                source.strip(), target.strip(), case_sensitive
            ),
            "Glossary term saved",
        )

    def _remove_glossary_term(self) -> None:
        item = self._glossary_list.currentItem()
        term = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(term, GlossaryTerm):
            return
        if QMessageBox.question(
            self,
            "Remove glossary term",
            f"Remove {term.source!r} -> {term.target!r}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._run_project_action(
            lambda: self._workspace.remove_glossary_term(term),
            "Glossary term removed",
        )

    def _import_glossary_csv(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        path_name, _ = QFileDialog.getOpenFileName(
            self, "Import glossary CSV", "", "CSV files (*.csv)"
        )
        if not path_name:
            return
        self._run_project_action(
            lambda: self._workspace.import_glossary_csv(Path(path_name)),
            "Glossary CSV imported",
        )

    def _export_glossary_csv(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        path_name, _ = QFileDialog.getSaveFileName(
            self, "Export glossary CSV", "", "CSV files (*.csv)"
        )
        if not path_name:
            return
        destination = Path(path_name)
        if destination.suffix.lower() != ".csv":
            destination = destination.with_suffix(".csv")
        self._run_project_action(
            lambda: self._workspace.export_glossary_csv(destination),
            "Glossary CSV exported",
        )

    def _translate_selected(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        entry_ids = self._selected_entry_ids()
        if not entry_ids:
            QMessageBox.information(self, "Batch translation", "Select one or more rows")
            return
        self._start_translation(entry_ids)

    def _translate_all_untranslated(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        entry_ids = self._workspace.untranslated_entry_ids()
        if not entry_ids:
            QMessageBox.information(
                self,
                "Batch translation",
                "There are no untranslated entries to translate.",
            )
            return
        self._start_translation(entry_ids)

    def _start_translation(self, entry_ids: tuple[str, ...]) -> None:
        worker = BatchTranslationWorker(
            lambda progress, is_cancelled: self._workspace.translate_entries(
                entry_ids,
                progress_callback=progress,
                cancellation_check=is_cancelled,
            ),
            self,
        )
        worker.succeeded.connect(self._translation_succeeded)
        worker.failed.connect(self._translation_failed)
        worker.progress.connect(self._translation_progress)
        worker.finished.connect(worker.deleteLater)
        self._translation_worker = worker
        self._set_busy(True)
        worker.start()

    def _validate_project(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        worker = ValidationWorker(self._workspace.validate_project, self)
        worker.succeeded.connect(self._validation_succeeded)
        worker.failed.connect(self._validation_failed)
        worker.finished.connect(worker.deleteLater)
        self._validation_worker = worker
        self._set_busy(True)
        self._cancel_button.setEnabled(False)
        self.statusBar().showMessage("Validating project...")
        worker.start()

    def _validation_succeeded(self, result_object: object) -> None:
        self._validation_worker = None
        self._set_busy(False, refresh=False)
        if not isinstance(result_object, ProjectValidationResult):
            QMessageBox.critical(self, "Validation", "Worker returned an invalid result")
            return
        self._refresh_project(select_first=False)
        self._sync_autosave()
        self.statusBar().showMessage(
            "Project validation completed: "
            f"{result_object.entries_checked} checked, "
            f"{result_object.entries_with_issues} with issues",
            5000,
        )

    def _validation_failed(self, message: str) -> None:
        self._validation_worker = None
        self._set_busy(False)
        QMessageBox.critical(self, "Validation failed", message)

    def _replace_translations(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        search_text, accepted = QInputDialog.getText(
            self, "Replace translations", "Find in translations:"
        )
        if not accepted or not search_text:
            return
        replacement_text, accepted = QInputDialog.getText(
            self, "Replace translations", "Replace with:"
        )
        if not accepted:
            return
        if QMessageBox.question(
            self,
            "Replace translations",
            "Replace all matching text in unlocked translations?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._run_project_action(
            lambda: self._workspace.replace_translations(search_text, replacement_text),
            "Translations replaced",
        )

    def _approve_selected(self) -> None:
        self._apply_bulk_approval(True)

    def _review_selected(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        entry_ids = self._selected_entry_ids()
        if not entry_ids:
            QMessageBox.information(self, "AI review", "Select one or more rows")
            return
        self._start_review(entry_ids)

    def _review_all(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        entry_ids = self._workspace.reviewable_entry_ids()
        if not entry_ids:
            QMessageBox.information(
                self, "AI review", "There are no unlocked Needs review entries"
            )
            return
        self._start_review(entry_ids)

    def _start_review(self, entry_ids: tuple[str, ...]) -> None:
        worker = ReviewWorker(
            lambda progress, is_cancelled: self._workspace.review_entries(
                entry_ids,
                progress_callback=progress,
                cancellation_check=is_cancelled,
            ),
            self,
        )
        worker.succeeded.connect(self._review_succeeded)
        worker.failed.connect(self._review_failed)
        worker.progress.connect(self._review_progress)
        worker.finished.connect(worker.deleteLater)
        self._review_worker = worker
        self._set_busy(True)
        self.statusBar().showMessage(f"Reviewing {len(entry_ids)} entries...")
        worker.start()

    def _review_succeeded(self, result_object: object) -> None:
        self._review_worker = None
        self._set_busy(False, refresh=False)
        if not isinstance(result_object, ReviewBatchResult):
            QMessageBox.critical(self, "AI review", "Worker returned an invalid result")
            return
        self._refresh_project(select_first=False)
        if result_object.cancelled:
            message = f"AI review cancelled after {result_object.reviewed_entries} entries"
        else:
            message = f"AI review completed: {result_object.issue_count} issue(s)"
        self.statusBar().showMessage(message, 5000)
        self._sync_autosave()

    def _review_progress(self, completed: int, total: int) -> None:
        self._progress.setRange(0, max(total, 1))
        self._progress.setValue(completed)
        self.statusBar().showMessage(f"Reviewing {completed} of {total}")

    def _review_failed(self, message: str) -> None:
        self._review_worker = None
        self._set_busy(False)
        QMessageBox.critical(self, "AI review failed", message)

    def _dismiss_ai_review_issue(self) -> None:
        if self._current_entry_id is None:
            return
        entry_id = self._current_entry_id
        self._run_project_action(
            lambda: self._workspace.dismiss_ai_review_issue(entry_id),
            "AI review issue dismissed",
        )

    def _retranslate_current_entry(self) -> None:
        if self._current_entry_id is not None and not self._current_entry_locked:
            self._start_translation((self._current_entry_id,))

    def _reopen_selected(self) -> None:
        self._apply_bulk_approval(False)

    def _lock_selected(self) -> None:
        self._apply_bulk_lock(True)

    def _unlock_selected(self) -> None:
        self._apply_bulk_lock(False)

    def _apply_bulk_approval(self, approved: bool) -> None:
        entry_ids = self._selected_entry_ids()
        if not entry_ids:
            QMessageBox.information(self, "Review", "Select one or more rows")
            return
        self._run_project_action(
            lambda: self._workspace.set_entries_approval(entry_ids, approved),
            "Selected translations approved"
            if approved
            else "Selected translations reopened for review",
        )

    def _apply_bulk_lock(self, locked: bool) -> None:
        entry_ids = self._selected_entry_ids()
        if not entry_ids:
            QMessageBox.information(self, "Review", "Select one or more rows")
            return
        self._run_project_action(
            lambda: self._workspace.set_entries_locked(entry_ids, locked),
            "Selected translations locked"
            if locked
            else "Selected translations unlocked",
        )

    def _selected_entry_ids(self) -> tuple[str, ...]:
        selected_rows = sorted(
            {index.row() for index in self._table.selectionModel().selectedRows()}
        )
        return tuple(
            self._model.entry_at(
                self._proxy_model.mapToSource(self._proxy_model.index(row, 0)).row()
            ).id
            for row in selected_rows
        )

    def _cancel_translation(self) -> None:
        if self._translation_worker is not None and self._translation_worker.isRunning():
            self._translation_worker.requestInterruption()
            operation = "translation"
        elif self._review_worker is not None and self._review_worker.isRunning():
            self._review_worker.requestInterruption()
            operation = "AI review"
        else:
            return
        self._cancel_button.setEnabled(False)
        self.statusBar().showMessage(
            f"Cancelling {operation} after the current Ollama request..."
        )

    def _translation_progress(self, completed: int, total: int) -> None:
        self._progress.setRange(0, max(total, 1))
        self._progress.setValue(completed)
        self.statusBar().showMessage(f"Translating {completed} of {total}")

    def _open_ollama_settings(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        try:
            models = self._workspace.list_models()
            status_message = f"Connected — {len(models)} model(s) found"
        except Exception as error:
            models = ()
            status_message = f"Unavailable — {error}"
        dialog = OllamaSettingsDialog(
            self._workspace.project.model_settings,
            models,
            status_message,
            self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self._run_project_action(
            lambda: self._workspace.update_model_settings(dialog.model_settings()),
            "Ollama settings updated",
        )

    def _translation_succeeded(self, result_object: object) -> None:
        self._translation_worker = None
        self._set_busy(False, refresh=False)
        if not isinstance(result_object, BatchResult):
            QMessageBox.critical(self, "Batch translation", "Worker returned an invalid result")
            return
        self._refresh_project(select_first=False)
        translated_count = len(result_object.translated_entry_ids)
        if result_object.cancelled:
            self.statusBar().showMessage(
                f"Translation cancelled after {translated_count} completed entries", 5000
            )
        else:
            self.statusBar().showMessage(f"Translated {translated_count} entries", 5000)
        if result_object.errors:
            QMessageBox.warning(
                self,
                "Batch translation completed with errors",
                "\n".join(result_object.errors),
            )
        self._sync_autosave()

    def _translation_failed(self, message: str) -> None:
        self._translation_worker = None
        self._set_busy(False)
        QMessageBox.critical(self, "Batch translation failed", message)

    def _on_current_row_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        del previous
        if not current.isValid():
            self._clear_editor()
            return
        source_index = self._proxy_model.mapToSource(current)
        entry = self._model.entry_at(source_index.row())
        self._current_entry_id = entry.id
        self._current_entry_locked = entry.locked
        self._current_entry_max_length = entry.max_length
        self._source_editor.setPlainText(entry.source)
        self._translation_editor.setPlainText(entry.translation or "")
        self._translation_editor.setReadOnly(entry.locked)
        self._copy_source_button.setEnabled(not entry.locked and not self._busy)
        self._apply_button.setEnabled(not entry.locked and not self._busy)
        self._approve_button.setText(
            "Reopen review" if entry.status is EntryStatus.APPROVED else "Approve"
        )
        self._approve_button.setEnabled(
            not self._busy
            and entry.translation is not None
            and (
                entry.status is EntryStatus.APPROVED
                or entry.status is not EntryStatus.ERROR
            )
        )
        self._lock_button.setChecked(entry.locked)
        self._lock_button.setEnabled(not self._busy and entry.translation is not None)
        self._refresh_current_entry_issues()
        self._refresh_translation_memory(entry.id)
        self._refresh_entry_history(entry.id)

    def _refresh_project(self, select_first: bool = True) -> None:
        has_project = self._workspace.has_project
        self._invalidate_translation_memory_cache()
        entries = self._workspace.project.entries if has_project else []
        self._model.set_entries(entries)
        self._update_status_filter_counts()
        self._refresh_filter_result_count()
        self._update_filter_controls()
        self._refresh_project_explorer()
        self._refresh_validation_issues()
        self._refresh_glossary()
        project_actions_enabled = has_project and not self._busy
        self._import_action.setEnabled(not self._busy)
        self._import_po_action.setEnabled(not self._busy)
        self._import_csv_action.setEnabled(not self._busy)
        self._import_xml_action.setEnabled(not self._busy)
        self._open_action.setEnabled(not self._busy)
        self._save_action.setEnabled(project_actions_enabled)
        self._save_as_action.setEnabled(project_actions_enabled)
        source_format = self._workspace.source_format if has_project else None
        self._export_action.setEnabled(
            project_actions_enabled and source_format == "json"
        )
        self._export_po_action.setEnabled(
            project_actions_enabled and source_format == "po"
        )
        self._export_csv_action.setEnabled(
            project_actions_enabled and source_format == "csv"
        )
        self._export_xml_action.setEnabled(
            project_actions_enabled and source_format == "xml"
        )
        self._translate_button.setEnabled(project_actions_enabled)
        self._settings_button.setEnabled(project_actions_enabled)
        self._translate_all_action.setEnabled(project_actions_enabled)
        self._replace_translations_action.setEnabled(project_actions_enabled)
        self._approve_selected_action.setEnabled(project_actions_enabled)
        self._review_selected_action.setEnabled(project_actions_enabled)
        self._review_all_action.setEnabled(project_actions_enabled)
        self._reopen_selected_action.setEnabled(project_actions_enabled)
        self._lock_selected_action.setEnabled(project_actions_enabled)
        self._unlock_selected_action.setEnabled(project_actions_enabled)
        self._validate_project_action.setEnabled(project_actions_enabled)
        self._issues_only_filter.setEnabled(project_actions_enabled)
        self._glossary_add_button.setEnabled(project_actions_enabled)
        self._glossary_import_button.setEnabled(project_actions_enabled)
        self._glossary_export_button.setEnabled(project_actions_enabled)
        self._glossary_remove_button.setEnabled(False)
        self._table.setEnabled(not self._busy)
        self._translation_editor.setEnabled(not self._busy)
        self._approve_button.setEnabled(False)
        self._lock_button.setEnabled(False)
        self._restore_history_button.setEnabled(False)
        self._apply_memory_button.setEnabled(False)
        self._copy_source_button.setEnabled(False)
        self._apply_button.setEnabled(False)
        self._clear_editor()
        if has_project:
            self._model_name.setText(self._workspace.project.model_settings.model)
            dirty_mark = " *" if self._workspace.project.dirty else ""
            self.setWindowTitle(f"LocaForge — {self._workspace.project.name}{dirty_mark}")
            if select_first and self._proxy_model.rowCount():
                self._table.selectRow(0)
        else:
            self._model_name.setText("Not configured")
            self.setWindowTitle("LocaForge")

    def _refresh_project_sidebars(self) -> None:
        if not self._workspace.has_project:
            return
        self._refresh_project_explorer()
        self._refresh_validation_issues()

    def _refresh_project_explorer(self) -> None:
        self._project_explorer.clear()
        if not self._workspace.has_project:
            self._project_explorer.addItem("No project open")
            return
        project = self._workspace.project
        statistics = self._workspace.project_statistics()
        self._project_explorer.addItem(project.name)
        self._project_explorer.addItem(
            f"{project.source_language} -> {project.target_language}"
        )
        self._project_explorer.addItem(
            f"Progress: {statistics.completion_percent}% "
            f"({statistics.translated_entries}/{statistics.total_entries})"
        )
        self._project_explorer.addItem(f"Untranslated: {statistics.untranslated_entries}")
        self._project_explorer.addItem(f"Needs review: {statistics.needs_review_entries}")
        self._project_explorer.addItem(f"Approved: {statistics.approved_entries}")
        self._project_explorer.addItem(f"Errors: {statistics.error_entries}")
        self._project_explorer.addItem(f"Validation issues: {statistics.entries_with_issues}")
        self._project_explorer.addItem(f"Locked: {statistics.locked_entries}")

    def _clear_editor(self) -> None:
        self._current_entry_id = None
        self._current_entry_locked = False
        self._current_entry_max_length = None
        self._source_editor.clear()
        self._translation_editor.clear()
        self._translation_editor.setReadOnly(False)
        self._current_issues.setText("No validation issues")
        self._dismiss_ai_issue_button.setEnabled(False)
        self._retranslate_button.setEnabled(False)
        self._apply_matching_button.setEnabled(False)
        self._copy_source_button.setEnabled(False)
        self._apply_button.setEnabled(False)
        self._approve_button.setText("Approve")
        self._approve_button.setEnabled(False)
        self._lock_button.setChecked(False)
        self._lock_button.setEnabled(False)
        self._history_list.clear()
        self._restore_history_button.setEnabled(False)
        self._translation_memory_suggestion = None
        self._pending_memory_entry_id = None
        self._memory_lookup_timer.stop()
        self._memory_request_id += 1
        self._translation_memory_list.clear()
        self._apply_memory_button.setEnabled(False)

    def _refresh_translation_length(self) -> None:
        self._translation_length.setText(
            format_translation_length(
                len(self._translation_editor.toPlainText()),
                self._current_entry_max_length,
            )
        )

    def _refresh_translation_memory(self, entry_id: str) -> None:
        self._translation_memory_list.clear()
        self._translation_memory_suggestion = None
        self._apply_memory_button.setEnabled(False)
        self._memory_request_id += 1
        cached_matches = self._translation_memory_cache.get(entry_id)
        if cached_matches is not None:
            self._display_translation_memory_matches(cached_matches)
            return
        self._pending_memory_entry_id = entry_id
        self._memory_lookup_timer.start()

    def _start_pending_translation_memory_lookup(self) -> None:
        if self._translation_memory_worker is not None:
            return
        if self._pending_memory_entry_id is None:
            return
        entry_id = self._pending_memory_entry_id
        self._pending_memory_entry_id = None
        self._start_translation_memory_lookup(entry_id, self._memory_request_id)

    def _start_translation_memory_lookup(self, entry_id: str, request_id: int) -> None:
        worker = TranslationMemoryWorker(
            request_id,
            lambda: self._workspace.translation_memory_matches(entry_id),
            self,
        )
        worker.succeeded.connect(self._translation_memory_loaded)
        worker.failed.connect(self._translation_memory_failed)
        worker.finished.connect(self._translation_memory_finished)
        worker.finished.connect(worker.deleteLater)
        self._translation_memory_worker = worker
        worker.start()

    def _translation_memory_loaded(self, request_id: int, matches_object: object) -> None:
        if request_id != self._memory_request_id or not isinstance(matches_object, tuple):
            return
        matches = tuple(
            match for match in matches_object if isinstance(match, TranslationMemoryMatch)
        )
        if self._current_entry_id is not None:
            if len(self._translation_memory_cache) >= 64:
                self._translation_memory_cache.pop(next(iter(self._translation_memory_cache)))
            self._translation_memory_cache[self._current_entry_id] = matches
        self._display_translation_memory_matches(matches)

    def _display_translation_memory_matches(
        self, matches: tuple[TranslationMemoryMatch, ...]
    ) -> None:
        for match in matches:
            context = f" [{match.record.context}]" if match.record.context else ""
            item = QListWidgetItem(
                f"{match.score:.0%} | {match.record.source}{context}\n"
                f"{match.record.translation}"
            )
            item.setData(Qt.ItemDataRole.UserRole, match.record.translation)
            self._translation_memory_list.addItem(item)
        if self._translation_memory_list.count():
            self._translation_memory_list.setCurrentRow(0)
        else:
            self._translation_memory_suggestion = None
            self._apply_memory_button.setEnabled(False)

    def _invalidate_translation_memory_cache(self) -> None:
        self._translation_memory_cache.clear()
        self._pending_memory_entry_id = None
        self._memory_lookup_timer.stop()
        self._memory_request_id += 1

    def _translation_memory_failed(self, request_id: int, message: str) -> None:
        if request_id == self._memory_request_id:
            logger.warning("Translation memory lookup failed: %s", message)

    def _translation_memory_finished(self) -> None:
        self._translation_memory_worker = None
        if self._pending_memory_entry_id is None:
            return
        self._start_pending_translation_memory_lookup()

    def _select_memory_suggestion(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        del previous
        translation = (
            current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        )
        self._translation_memory_suggestion = (
            translation if isinstance(translation, str) else None
        )
        self._apply_memory_button.setEnabled(
            self._translation_memory_suggestion is not None
            and not self._current_entry_locked
            and not self._busy
        )

    def _activate_memory_suggestion(self, item: QListWidgetItem) -> None:
        self._translation_memory_list.setCurrentItem(item)
        self._apply_memory_suggestion()

    def _refresh_entry_history(self, entry_id: str) -> None:
        self._history_list.clear()
        for revision in self._workspace.entry_revisions(entry_id):
            timestamp = revision.recorded_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            translation = (
                revision.translation.replace("\n", " ")
                if revision.translation is not None
                else "<untranslated>"
            )
            item = QListWidgetItem(f"{timestamp} | {translation}")
            item.setData(Qt.ItemDataRole.UserRole, revision.revision_id)
            self._history_list.addItem(item)

    def _on_history_selection_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        del previous
        self._restore_history_button.setEnabled(
            current is not None
            and self._current_entry_id is not None
            and not self._current_entry_locked
            and not self._busy
        )

    def _activate_history_revision(self, item: QListWidgetItem) -> None:
        self._history_list.setCurrentItem(item)
        self._restore_history_revision()

    def _refresh_validation_issues(self) -> None:
        self._validation_list.clear()
        self._validation_issues_by_entry.clear()
        if not self._workspace.has_project:
            self._update_issue_filter_label()
            return
        entries_by_id = {entry.id: entry for entry in self._workspace.project.entries}
        all_issues = self._workspace.validation_issues()
        grouped_issues: dict[str, list[EntryValidationIssue]] = {}
        for issue in all_issues:
            grouped_issues.setdefault(issue.entry_id, []).append(issue)
        self._validation_issues_by_entry = {
            entry_id: tuple(issues) for entry_id, issues in grouped_issues.items()
        }
        self._update_issue_filter_label()
        if self._issues_only_filter.isChecked():
            self._proxy_model.set_issue_entry_ids(self._validation_issues_by_entry)
        category = self._validation_filter.currentData()
        issues = filter_validation_issues(
            all_issues,
            category if isinstance(category, str) else None,
        )
        if category == "attention":
            issue_groups = group_attention_issues(issues)
        else:
            issue_groups = tuple(
                group_attention_issues((issue,))[0] for issue in issues
            )
        for issue_group in issue_groups:
            entry = entries_by_id.get(issue_group.entry_ids[0])
            path = (
                "/".join(str(part) for part in entry.key_path)
                if entry is not None
                else issue_group.entry_ids[0]
            )
            if len(issue_group.entry_ids) > 1:
                source = entry.source.replace("\n", " ") if entry is not None else path
                item_text = (
                    f"{len(issue_group.entry_ids)} entries | {source} — "
                    f"[{issue_group.code.value}] {issue_group.message}"
                )
            else:
                item_text = (
                    f"{path} — [{issue_group.code.value}] {issue_group.message}"
                )
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, issue_group.entry_ids)
            self._validation_list.addItem(item)
        self._refresh_current_entry_issues()

    def _refresh_current_entry_issues(self) -> None:
        if self._current_entry_id is None:
            self._current_issues.setText("No validation issues")
            self._dismiss_ai_issue_button.setEnabled(False)
            self._retranslate_button.setEnabled(False)
            return
        issues = self._validation_issues_by_entry.get(self._current_entry_id, ())
        self._current_issues.setText(format_validation_issues(issues))
        self._dismiss_ai_issue_button.setEnabled(
            not self._busy
            and any(issue.code is ValidationCode.AI_REVIEW for issue in issues)
        )
        entry = self._workspace.project.get_entry(self._current_entry_id)
        self._retranslate_button.setEnabled(
            not self._busy
            and not entry.locked
            and entry.status is not EntryStatus.APPROVED
        )
        matching_count = sum(
            not matching_entry.locked
            and matching_entry.source == entry.source
            and matching_entry.context == entry.context
            for matching_entry in self._workspace.project.entries
        )
        self._apply_matching_button.setEnabled(
            not self._busy
            and not entry.locked
            and entry.translation is not None
            and matching_count > 1
            and any(
                issue.code is ValidationCode.INCONSISTENT_TRANSLATION
                for issue in issues
            )
        )

    def _refresh_glossary(self) -> None:
        self._glossary_list.clear()
        if not self._workspace.has_project:
            return
        for term in self._workspace.glossary_terms():
            sensitivity = " [case-sensitive]" if term.case_sensitive else ""
            item = QListWidgetItem(f"{term.source} -> {term.target}{sensitivity}")
            item.setData(Qt.ItemDataRole.UserRole, term)
            self._glossary_list.addItem(item)

    def _on_glossary_selection_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        del previous
        self._glossary_remove_button.setEnabled(
            current is not None and self._workspace.has_project and not self._busy
        )

    def _activate_validation_issue(self, item: QListWidgetItem) -> None:
        entry_ids = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(entry_ids, tuple) or not entry_ids:
            return
        entry_id = entry_ids[0]
        if not isinstance(entry_id, str):
            return
        self._select_entry_by_id(entry_id)

    def _select_entry_by_id(self, entry_id: str) -> None:
        self._search.clear()
        self._clear_status_filter()
        for row, entry in enumerate(self._workspace.project.entries):
            if entry.id != entry_id:
                continue
            proxy_index = self._proxy_model.mapFromSource(self._model.index(row, 0))
            if proxy_index.isValid():
                self._table.selectRow(proxy_index.row())
                self._table.scrollTo(proxy_index)
            return

    def _apply_issue_filter(self, enabled: bool) -> None:
        entry_ids = self._validation_issues_by_entry if enabled else None
        self._proxy_model.set_issue_entry_ids(entry_ids)
        self._update_filter_controls()

    def _run_project_action(
        self, action: Callable[[], object], success_message: str
    ) -> bool:
        if self._busy:
            return False
        try:
            action()
        except Exception as error:
            logger.exception("Project action failed")
            QMessageBox.critical(self, "LocaForge error", str(error))
            return False
        self._refresh_project()
        self._sync_autosave()
        self.statusBar().showMessage(success_message, 5000)
        return True

    def _run_entry_action(
        self, action: Callable[[], TranslationEntry], success_message: str
    ) -> bool:
        if self._busy:
            return False
        try:
            entry = action()
        except Exception as error:
            logger.exception("Entry action failed")
            QMessageBox.critical(self, "LocaForge error", str(error))
            return False
        self._invalidate_translation_memory_cache()
        self._model.update_entry(entry)
        self._update_status_filter_counts()
        dirty_mark = " *" if self._workspace.project.dirty else ""
        self.setWindowTitle(f"LocaForge — {self._workspace.project.name}{dirty_mark}")
        self._summary_refresh_timer.start()
        if self._current_entry_id == entry.id:
            self._refresh_translation_memory(entry.id)
        self._sync_autosave()
        self.statusBar().showMessage(success_message, 5000)
        return True

    def _remember_current_project(self) -> None:
        container_path = self._workspace.session.container_path
        if container_path is None:
            return
        self._recent_projects.add(container_path)
        self._refresh_recent_projects_menu()

    def _refresh_recent_projects_menu(self) -> None:
        self._recent_projects_menu.clear()
        paths = self._recent_projects.list_paths()
        if not paths:
            empty_action = self._recent_projects_menu.addAction("No recent projects")
            empty_action.setEnabled(False)
            return
        for project_path in paths:
            action = self._recent_projects_menu.addAction(
                f"{project_path.name} — {project_path.parent}"
            )
            action.triggered.connect(
                lambda checked=False, path=project_path: self._open_recent_project(path)
            )
        self._recent_projects_menu.addSeparator()
        clear_action = self._recent_projects_menu.addAction("Clear recent projects")
        clear_action.triggered.connect(self._clear_recent_projects)

    def _open_recent_project(self, project_path: Path) -> None:
        if not project_path.is_file():
            self._recent_projects.remove(project_path)
            self._refresh_recent_projects_menu()
            QMessageBox.information(
                self,
                "Recent project unavailable",
                f"The project file no longer exists:\n{project_path}",
            )
            return
        if not self._confirm_unsaved_changes():
            return
        if self._run_project_action(
            lambda: self._workspace.open(project_path), "Project opened"
        ):
            self._remember_current_project()

    def _clear_recent_projects(self) -> None:
        self._recent_projects.clear()
        self._refresh_recent_projects_menu()

    def _set_busy(self, busy: bool, refresh: bool = True) -> None:
        self._busy = busy
        if busy:
            self._autosave.cancel()
        self._progress.setVisible(busy)
        self._cancel_button.setVisible(busy)
        self._cancel_button.setEnabled(busy)
        if not busy:
            self._progress.setValue(0)
        if refresh:
            self._refresh_project()

    def _sync_autosave(self) -> None:
        if self._workspace.has_project and self._workspace.project.dirty:
            self._autosave.schedule()
        else:
            self._autosave.cancel()

    def _autosave_succeeded(self) -> None:
        self._workspace.refresh_after_autosave()
        self._refresh_project()
        self.statusBar().showMessage("Project autosaved", 3000)

    def _autosave_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Autosave failed", message)

    def _set_status_filter(self, status: str, selected: bool) -> None:
        del status, selected
        self._status_filter_timer.start()
        self._update_status_filter_label()
        self._update_filter_controls()

    def _apply_status_filter(self) -> None:
        selected_statuses = {
            value
            for value, action in self._status_filter_actions.items()
            if action.isChecked()
        }
        self._proxy_model.set_statuses(selected_statuses)

    def _clear_status_filter(self) -> None:
        self._status_filter_timer.stop()
        for action in self._status_filter_actions.values():
            action.blockSignals(True)
            action.setChecked(False)
            action.blockSignals(False)
        self._apply_status_filter()
        self._update_status_filter_label()

    def _set_search_filter(self, text: str) -> None:
        self._update_filter_controls()
        if not text.strip():
            self._search_filter_timer.stop()
            self._apply_search_filter()
            return
        self._search_filter_timer.start()

    def _apply_search_filter(self) -> None:
        self._proxy_model.set_search_text(self._search.text())

    def _clear_filters(self) -> None:
        self._search.clear()
        self._search_filter_timer.stop()
        self._apply_search_filter()
        self._clear_status_filter()
        self._issues_only_filter.setChecked(False)
        self._update_filter_controls()

    def _focus_search(self) -> None:
        self._search.setFocus()
        self._search.selectAll()

    def _update_filter_controls(self) -> None:
        has_filters = bool(self._search.text().strip()) or any(
            action.isChecked() for action in self._status_filter_actions.values()
        ) or self._issues_only_filter.isChecked()
        self._clear_filters_button.setEnabled(has_filters)

    def _refresh_filter_result_count(self) -> None:
        self._filter_result_count.setText(
            f"{self._proxy_model.rowCount()} / {self._model.rowCount()} entries"
        )

    def _update_status_filter_label(self) -> None:
        selected_actions = [
            action for action in self._status_filter_actions.values() if action.isChecked()
        ]
        if not selected_actions:
            self._status_filter.setText("All statuses")
        elif len(selected_actions) == 1:
            self._status_filter.setText(selected_actions[0].text())
        else:
            self._status_filter.setText(f"{len(selected_actions)} statuses")

    def _update_status_filter_counts(self) -> None:
        entries = self._workspace.project.entries if self._workspace.has_project else ()
        status_counts = Counter(entry.status.value for entry in entries)
        for status, action in self._status_filter_actions.items():
            action.setText(
                f"{self._status_filter_labels[status]} ({status_counts[status]})"
            )
        self._update_status_filter_label()

    def _update_issue_filter_label(self) -> None:
        self._issues_only_filter.setText(
            f"Issues only ({len(self._validation_issues_by_entry)})"
        )

    def _restore_window_layout(self) -> None:
        saved_layout = self._layout_store.load()
        if saved_layout is None:
            return
        geometry, state = saved_layout
        self.restoreGeometry(geometry)
        self.restoreState(state)

    def _persist_window_layout(self) -> None:
        self._layout_store.save(self.saveGeometry(), self.saveState())

    def _reset_window_layout(self) -> None:
        self._layout_store.clear()
        self.restoreGeometry(self._default_window_geometry)
        self.restoreState(self._default_window_state)
        self.statusBar().showMessage("Window layout reset", 3000)

    def _confirm_unsaved_changes(self) -> bool:
        if not self._workspace.has_project or not self._workspace.project.dirty:
            return True
        response = QMessageBox.question(
            self,
            "Unsaved changes",
            "Save changes to the current project?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if response == QMessageBox.StandardButton.Cancel:
            return False
        if response == QMessageBox.StandardButton.Discard:
            self._autosave.cancel()
            return True
        try:
            self._workspace.save()
        except Exception as error:
            logger.exception("Project save during close failed")
            QMessageBox.critical(self, "Cannot save project", str(error))
            return False
        self._autosave.cancel()
        return True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._translation_worker is not None and self._translation_worker.isRunning():
            QMessageBox.warning(
                self,
                "Translation in progress",
                "Wait for the current translation request to finish before closing LocaForge.",
            )
            event.ignore()
            return
        if self._review_worker is not None and self._review_worker.isRunning():
            QMessageBox.warning(
                self,
                "AI review in progress",
                "Wait for the current AI review request to finish before closing LocaForge.",
            )
            event.ignore()
            return
        if not self._confirm_unsaved_changes():
            event.ignore()
            return
        self._autosave.wait_for_completion()
        self._persist_window_layout()
        self._log_viewer.detach()
        super().closeEvent(event)

    def _ask_language(self, title: str, default: str) -> str | None:
        language, accepted = QInputDialog.getText(
            self, title, "Language code:", text=default
        )
        if not accepted or not language.strip():
            return None
        return language.strip()
