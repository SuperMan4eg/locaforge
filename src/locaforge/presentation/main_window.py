"""Main PySide6 window for the desktop MVP."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QModelIndex, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from locaforge.application.dto.validation import ValidationCode
from locaforge.application.project_workspace import ImportFieldMapping, ProjectWorkspace
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.settings import ModelSettings
from locaforge.presentation.autosave_controller import AutosaveController
from locaforge.presentation.glossary_controller import GlossaryController
from locaforge.presentation.history_controller import HistoryController
from locaforge.presentation.import_mapping_controller import ImportMappingController
from locaforge.presentation.json_import_profiles import (
    JsonImportProfileStore,
)
from locaforge.presentation.log_viewer import LogViewerController
from locaforge.presentation.model_pull_controller import ModelPullController
from locaforge.presentation.model_settings_profile import ModelSettingsProfileStore
from locaforge.presentation.ollama_settings_dialog import OllamaSettingsDialog
from locaforge.presentation.project_explorer_controller import ProjectExplorerController
from locaforge.presentation.project_io_controller import ProjectIoController
from locaforge.presentation.project_setup_dialog import ProjectSetupDialog
from locaforge.presentation.quality_panel_controller import QualityPanelController
from locaforge.presentation.recent_projects import RecentProjectsStore
from locaforge.presentation.recent_projects_controller import RecentProjectsController
from locaforge.presentation.review_controller import ReviewController
from locaforge.presentation.translation_controller import TranslationController
from locaforge.presentation.translation_filter_controller import TranslationFilterController
from locaforge.presentation.translation_filter_proxy import TranslationFilterProxyModel
from locaforge.presentation.translation_length import format_translation_length
from locaforge.presentation.translation_memory_controller import (
    TranslationMemoryController,
)
from locaforge.presentation.translation_memory_dialog import TranslationMemoryDialog
from locaforge.presentation.translation_navigation import (
    adjacent_row_index,
    next_matching_entry_id,
)
from locaforge.presentation.translation_table_model import TranslationTableModel
from locaforge.presentation.validation_controller import ValidationController
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
        self._recent: RecentProjectsController
        self._json_import_profiles = JsonImportProfileStore(QSettings())
        self._import_mappings = ImportMappingController(
            workspace, self._json_import_profiles, self
        )
        self._model_settings_profile = ModelSettingsProfileStore(QSettings())
        self._project_io = ProjectIoController(
            workspace,
            self._run_project_action,
            lambda: self._recent.remember_current(),
        )
        self._model = TranslationTableModel(self)
        self._proxy_model = TranslationFilterProxyModel()
        self._proxy_model.setSourceModel(self._model)
        self._current_entry_id: str | None = None
        self._current_entry_locked = False
        self._current_entry_max_length: int | None = None
        self._busy = False

        self._table = QTableView(self)
        self._table.setModel(self._proxy_model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSortingEnabled(True)
        self._table.selectionModel().currentRowChanged.connect(self._on_current_row_changed)

        self._filters = TranslationFilterController(self._model, self._proxy_model, self)
        self._summary_refresh_timer = QTimer(self)
        self._summary_refresh_timer.setSingleShot(True)
        self._summary_refresh_timer.setInterval(500)
        self._summary_refresh_timer.timeout.connect(self._refresh_project_sidebars)
        filter_layout = QHBoxLayout()
        self._filters.add_to_layout(filter_layout)
        table_widget = QWidget(self)
        table_layout = QVBoxLayout(table_widget)
        table_layout.addLayout(filter_layout)
        table_layout.addWidget(self._table)

        self._source_editor = QPlainTextEdit(self)
        self._source_editor.setReadOnly(True)
        self._translation_editor = QPlainTextEdit(self)
        self._model_candidate = QPlainTextEdit(self)
        self._model_candidate.setReadOnly(True)
        self._model_candidate.setPlaceholderText("No translation-model version")
        self._reviewer_candidate = QPlainTextEdit(self)
        self._reviewer_candidate.setReadOnly(True)
        self._reviewer_candidate.setPlaceholderText("No reviewer suggestion")
        self._use_model_candidate_button = QPushButton("Use model version", self)
        self._use_model_candidate_button.setToolTip(
            "Make the translation model's version the active translation"
        )
        self._use_model_candidate_button.clicked.connect(
            lambda: self._select_translation_candidate("model")
        )
        self._use_reviewer_candidate_button = QPushButton("Use reviewer version", self)
        self._use_reviewer_candidate_button.setToolTip(
            "Make the reviewer's corrected version the active translation"
        )
        self._use_reviewer_candidate_button.clicked.connect(
            lambda: self._select_translation_candidate("reviewer")
        )
        self._translation_length = QLabel("Characters: 0", self)
        self._translation_editor.textChanged.connect(self._refresh_translation_length)
        self._current_issues = QLabel("No validation issues", self)
        self._current_issues.setWordWrap(True)
        self._current_issues.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._dismiss_ai_issue_button = QPushButton("Dismiss AI issue", self)
        self._dismiss_ai_issue_button.setToolTip(
            "Dismiss the AI reviewer issue for the current entry"
        )
        self._dismiss_ai_issue_button.clicked.connect(self._dismiss_ai_review_issue)
        self._retranslate_button = QPushButton("Re-translate", self)
        self._retranslate_button.setToolTip("Translate the current entry again with Ollama")
        self._retranslate_button.clicked.connect(self._retranslate_current_entry)
        self._apply_matching_button = QPushButton(
            "Apply to matching source", self
        )
        self._apply_matching_button.setToolTip(
            "Apply this translation to every unlocked entry with identical source text"
        )
        self._apply_matching_button.clicked.connect(self._apply_translation_to_matches)
        self._copy_source_button = QPushButton("Copy source", self)
        self._copy_source_button.setToolTip("Copy the source text into the translation editor")
        self._copy_source_button.clicked.connect(self._copy_source_to_translation)
        self._apply_button = QPushButton("Apply translation", self)
        self._apply_button.clicked.connect(self._apply_translation)
        self._apply_button.setToolTip("Save the edited translation (Ctrl+Enter)")
        self._approve_button = QPushButton("Approve", self)
        self._approve_button.setToolTip("Approve or reopen the current translation")
        self._approve_button.clicked.connect(self._toggle_entry_approval)
        self._lock_button = QPushButton("Locked", self)
        self._lock_button.setToolTip("Prevent or allow changes to the current translation")
        self._lock_button.setCheckable(True)
        self._lock_button.clicked.connect(self._set_entry_locked)
        self._model_name = QLabel("qwen3", self)
        self._settings_button = QPushButton("Settings...", self)
        self._settings_button.setToolTip("Configure translation and reviewer models")
        self._settings_button.clicked.connect(self._open_ollama_settings)
        self._translate_button = QPushButton("Translate selected", self)
        self._translate_button.setToolTip("Translate the selected unlocked entries")
        self._translate_button.clicked.connect(self._translate_selected)
        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.setToolTip("Cancel the operation after the current model request")
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
        candidates_layout = QHBoxLayout()
        model_candidate_layout = QVBoxLayout()
        model_candidate_layout.addWidget(QLabel("Translation model version", self))
        model_candidate_layout.addWidget(self._model_candidate)
        model_candidate_layout.addWidget(self._use_model_candidate_button)
        reviewer_candidate_layout = QVBoxLayout()
        reviewer_candidate_layout.addWidget(QLabel("Reviewer version", self))
        reviewer_candidate_layout.addWidget(self._reviewer_candidate)
        reviewer_candidate_layout.addWidget(self._use_reviewer_candidate_button)
        candidates_layout.addLayout(model_candidate_layout)
        candidates_layout.addLayout(reviewer_candidate_layout)
        editor_layout.addLayout(candidates_layout)
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
        self._validation_filter = QComboBox(self)
        self._validation_filter.addItem("All issues", None)
        self._validation_filter.addItem("Requires attention", "attention")
        self._validation_filter.addItem("AI Reviewer", "ai_review")
        self._validation_filter.addItem("Consistency", "consistency")
        self._validation_filter.addItem("Structural", "structural")
        validation_widget = QWidget(self)
        validation_layout = QVBoxLayout(validation_widget)
        validation_layout.addWidget(self._validation_filter)
        validation_layout.addWidget(self._validation_list)
        validation_dock = QDockWidget("Validation", self)
        validation_dock.setObjectName("validation_dock")
        validation_dock.setWidget(validation_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, validation_dock)

        self._history_list = QListWidget(self)
        self._restore_history_button = QPushButton("Restore revision", self)
        self._restore_history_button.setToolTip(
            "Restore the selected earlier translation of the current entry"
        )
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
        self._clear_log_button.setToolTip("Remove all messages currently shown in the log panel")
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
        self._apply_memory_button = QPushButton("Apply TM suggestion", self)
        self._apply_memory_button.setToolTip(
            "Use the selected translation-memory suggestion for the current entry"
        )
        memory_widget = QWidget(self)
        memory_layout = QVBoxLayout(memory_widget)
        memory_layout.addWidget(self._translation_memory_list)
        memory_layout.addWidget(self._apply_memory_button)
        memory_dock = QDockWidget("Translation Memory", self)
        memory_dock.setObjectName("translation_memory_dock")
        memory_dock.setWidget(memory_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, memory_dock)

        self._glossary_list = QListWidget(self)
        self._glossary_add_button = QPushButton("Add term...", self)
        self._glossary_remove_button = QPushButton("Remove term", self)
        self._glossary_import_button = QPushButton("Import CSV...", self)
        self._glossary_export_button = QPushButton("Export CSV...", self)
        self._glossary_add_button.setToolTip("Add a term for the project's language pair")
        self._glossary_remove_button.setToolTip("Remove the selected glossary term")
        self._glossary_import_button.setToolTip("Import glossary terms from a CSV file")
        self._glossary_export_button.setToolTip("Export glossary terms to a CSV file")
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
        self._export_all_action = QAction("Export &all project files...", self)
        self._export_all_action.setToolTip(
            "Export every document with its original file name and format"
        )
        self._export_all_action.triggered.connect(self._export_all_documents)
        self._build_menu()

        self._autosave = AutosaveController(self._workspace.autosave, parent=self)
        self._autosave.saved.connect(self._autosave_succeeded)
        self._autosave.failed.connect(self._autosave_failed)
        self._review = ReviewController(
            workspace=self._workspace,
            ensure_model=self._ensure_model_available,
            set_busy=lambda busy, refresh: self._set_busy(busy, refresh),
            refresh_project=lambda select_first: self._refresh_project(select_first),
            sync_autosave=self._sync_autosave,
            show_status=lambda message, timeout: self.statusBar().showMessage(
                message, timeout
            ),
            show_error=self._show_review_error,
            show_progress=self._review_progress,
            parent=self,
        )
        self._translation = TranslationController(
            workspace=self._workspace,
            ensure_model=self._ensure_model_available,
            set_busy=lambda busy, refresh: self._set_busy(busy, refresh),
            refresh_project=lambda select_first: self._refresh_project(select_first),
            sync_autosave=self._sync_autosave,
            show_status=lambda message, timeout: self.statusBar().showMessage(
                message, timeout
            ),
            show_error=self._show_translation_error,
            show_warning=self._show_translation_warning,
            show_progress=self._translation_progress,
            parent=self,
        )
        self._validation = ValidationController(
            workspace=self._workspace,
            set_busy=lambda busy, refresh: self._set_busy(busy, refresh),
            refresh_project=lambda select_first: self._refresh_project(select_first),
            sync_autosave=self._sync_autosave,
            disable_cancel=lambda: self._cancel_button.setEnabled(False),
            show_status=lambda message, timeout: self.statusBar().showMessage(
                message, timeout
            ),
            show_error=self._show_validation_error,
            parent=self,
        )
        self._model_pull = ModelPullController(
            workspace=self._workspace,
            set_busy=lambda busy, refresh: self._set_busy(busy, refresh),
            prepare_progress=self._prepare_model_pull_progress,
            show_status=lambda message, timeout: self.statusBar().showMessage(
                message, timeout
            ),
            show_error=self._show_model_pull_error,
            parent=self,
        )
        self._memory = TranslationMemoryController(
            workspace=self._workspace,
            suggestions=self._translation_memory_list,
            apply_button=self._apply_memory_button,
            can_apply=lambda: not self._current_entry_locked and not self._busy,
            apply_suggestion=self._apply_memory_suggestion,
            parent=self,
        )
        self._glossary = GlossaryController(
            workspace=self._workspace,
            terms=self._glossary_list,
            add_button=self._glossary_add_button,
            remove_button=self._glossary_remove_button,
            import_button=self._glossary_import_button,
            export_button=self._glossary_export_button,
            run_action=self._run_project_action,
            source_text=self._source_editor.toPlainText,
            translation_text=self._translation_editor.toPlainText,
            is_busy=lambda: self._busy,
            parent=self,
        )
        self._history = HistoryController(
            workspace=self._workspace,
            revisions=self._history_list,
            restore_button=self._restore_history_button,
            run_action=self._run_project_action,
            current_entry_id=lambda: self._current_entry_id,
            can_restore=lambda: (
                self._current_entry_id is not None
                and not self._current_entry_locked
                and not self._busy
            ),
            parent=self,
        )
        self._project_overview = ProjectExplorerController(
            self._workspace, self._project_explorer, self
        )
        self._quality = QualityPanelController(
            workspace=self._workspace,
            category_filter=self._validation_filter,
            issue_list=self._validation_list,
            current_issues=self._current_issues,
            dismiss_ai_button=self._dismiss_ai_issue_button,
            retranslate_button=self._retranslate_button,
            apply_matching_button=self._apply_matching_button,
            table_filters=self._filters,
            current_entry_id=lambda: self._current_entry_id,
            is_busy=lambda: self._busy,
            select_entry=self._select_entry_by_id,
            parent=self,
        )
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
        self._import_multiple_action = QAction("Import &multiple files...", self)
        self._import_multiple_action.setToolTip(
            "Create one project from several JSON, CSV/TSV, PO, or XML files"
        )
        self._import_multiple_action.triggered.connect(self._import_multiple_files)
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

        file_menu.addAction(self._import_multiple_action)
        file_menu.addSeparator()
        file_menu.addAction(self._import_action)
        file_menu.addAction(self._import_po_action)
        file_menu.addAction(self._import_csv_action)
        file_menu.addAction(self._import_xml_action)
        file_menu.addAction(self._open_action)
        self._recent_projects_menu = file_menu.addMenu("Recent projects")
        self._recent = RecentProjectsController(
            workspace=self._workspace,
            store=self._recent_projects,
            menu=self._recent_projects_menu,
            run_action=self._run_project_action,
            confirm_unsaved=self._confirm_unsaved_changes,
            show_info=self._show_recent_project_info,
            parent=self,
        )
        self._recent.refresh()
        file_menu.addSeparator()
        file_menu.addAction(self._save_action)
        file_menu.addAction(self._save_as_action)
        file_menu.addAction(self._export_action)
        file_menu.addAction(self._export_po_action)
        file_menu.addAction(self._export_csv_action)
        file_menu.addAction(self._export_xml_action)
        file_menu.addAction(self._export_all_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        edit_menu = self.menuBar().addMenu("&Edit")
        self._undo_translation_action = QAction("Undo last translation", self)
        self._undo_translation_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_translation_action.setToolTip(
            "Restore every entry changed by the latest batch translation (Ctrl+Z)"
        )
        self._undo_translation_action.triggered.connect(self._undo_last_translation)
        edit_menu.addAction(self._undo_translation_action)

        review_menu = self.menuBar().addMenu("&Review")
        self._select_qa_entries_action = QAction("Select all QA entries", self)
        self._select_qa_entries_action.triggered.connect(self._select_all_qa_entries)
        self._retranslate_qa_entries_action = QAction(
            "Re-translate all QA entries", self
        )
        self._retranslate_qa_entries_action.triggered.connect(
            self._retranslate_all_qa_entries
        )
        self._dismiss_selected_ai_issues_action = QAction(
            "Dismiss AI issues for selected", self
        )
        self._dismiss_selected_ai_issues_action.triggered.connect(
            self._dismiss_selected_ai_issues
        )
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
        review_menu.addAction(self._select_qa_entries_action)
        review_menu.addAction(self._retranslate_qa_entries_action)
        review_menu.addAction(self._dismiss_selected_ai_issues_action)
        review_menu.addSeparator()
        review_menu.addAction(self._review_selected_action)
        review_menu.addAction(self._review_all_action)
        review_menu.addSeparator()
        review_menu.addAction(self._approve_selected_action)
        review_menu.addAction(self._reopen_selected_action)
        review_menu.addSeparator()
        review_menu.addAction(self._lock_selected_action)
        review_menu.addAction(self._unlock_selected_action)

        models_menu = self.menuBar().addMenu("&Models")
        self._model_settings_action = QAction("Model settings...", self)
        self._model_settings_action.setToolTip(
            "Configure the translation model, reviewer model, prompts, and timeouts"
        )
        self._model_settings_action.triggered.connect(self._open_ollama_settings)
        models_menu.addAction(self._model_settings_action)
        self._model_setup_action = QAction("Download or set up models...", self)
        self._model_setup_action.setToolTip("Check Ollama and download an installed model")
        self._model_setup_action.triggered.connect(self._open_ollama_setup)
        models_menu.addAction(self._model_setup_action)

        tools_menu = self.menuBar().addMenu("&Tools")
        self._ollama_setup_action = QAction("Ollama Setup...", self)
        self._ollama_setup_action.triggered.connect(self._open_ollama_setup)
        tools_menu.addAction(self._ollama_setup_action)
        self._translation_memory_action = QAction("Translation Memory...", self)
        self._translation_memory_action.triggered.connect(
            self._open_translation_memory_editor
        )
        tools_menu.addAction(self._translation_memory_action)
        tools_menu.addSeparator()
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
        self._focus_search_action.triggered.connect(self._filters.focus_search)
        self._focus_search_action.setShortcut(QKeySequence.StandardKey.Find)
        self.addAction(self._focus_search_action)
        self._clear_filters_action = QAction("Clear table filters", self)
        self._clear_filters_action.triggered.connect(self._filters.clear)
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

    def _import_multiple_files(self) -> None:
        source_names, _ = QFileDialog.getOpenFileNames(
            self,
            "Import localization files",
            "",
            "Localization files (*.json *.csv *.tsv *.po *.xml)",
        )
        if not source_names:
            return
        source_paths = tuple(Path(name) for name in source_names)
        field_mappings: dict[Path, ImportFieldMapping] = {}
        for source_path in source_paths:
            suffix = source_path.suffix.lower()
            if suffix == ".json":
                field_mappings[source_path] = self._import_mappings.ask_json(source_path)
            elif suffix in {".csv", ".tsv"}:
                mapping = self._import_mappings.ask_csv(source_path)
                if mapping is None:
                    return
                field_mappings[source_path] = mapping
            elif suffix == ".xml":
                field_mappings[source_path] = self._import_mappings.ask_xml(source_path)
        destination_name, _ = QFileDialog.getSaveFileName(
            self, "Create LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        if not destination_name:
            return
        formats = ", ".join(sorted({path.suffix.lower().lstrip(".") for path in source_paths}))
        languages = self._ask_project_setup(
            Path(f"{len(source_paths)} selected files"),
            Path(destination_name),
            formats,
            "Each file is stored as a separate project document; field mappings are "
            "applied per file and original file names are preserved.",
        )
        if languages is None or not self._confirm_unsaved_changes():
            return
        source_language, target_language = languages
        self._project_io.create_from_files(
            source_paths,
            Path(destination_name),
            source_language,
            target_language,
            field_mappings,
        )

    def _import_json(self) -> None:
        source_name, _ = QFileDialog.getOpenFileName(
            self, "Import JSON", "", "JSON files (*.json)"
        )
        if not source_name:
            return
        field_mapping = self._import_mappings.ask_json(Path(source_name))
        destination_name, _ = QFileDialog.getSaveFileName(
            self, "Create LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        if not destination_name:
            return
        mapping_description = (
            "Automatic: every string value is translated and its JSON path is used as the key"
            if field_mapping is None
            else (
                f"Source: {field_mapping.source_field}; target: {field_mapping.target_field}; "
                f"key: {field_mapping.key_field or 'generated JSON path'}"
            )
        )
        languages = self._ask_project_setup(
            Path(source_name), Path(destination_name), "JSON", mapping_description
        )
        if languages is None:
            return
        source_language, target_language = languages
        if not self._confirm_unsaved_changes():
            return
        self._project_io.create_from_json(
            Path(source_name),
            Path(destination_name),
            source_language,
            target_language,
            field_mapping,
        )

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
        languages = self._ask_project_setup(
            Path(source_name),
            Path(destination_name),
            "PO",
            "Gettext msgid is the source, msgstr is the translation, and "
            "comments/context are preserved",
        )
        if languages is None or not self._confirm_unsaved_changes():
            return
        source_language, target_language = languages
        self._project_io.create_from_po(
            Path(source_name), Path(destination_name), source_language, target_language
        )

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
        field_mapping = self._import_mappings.ask_csv(source_path)
        if field_mapping is None:
            return
        destination_name, _ = QFileDialog.getSaveFileName(
            self, "Create LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        if not destination_name:
            return
        languages = self._ask_project_setup(
            source_path,
            Path(destination_name),
            "CSV/TSV",
            f"Source: {field_mapping.source_field}; target: {field_mapping.target_field}; "
            f"key: {field_mapping.key_field or 'generated row number'}",
        )
        if languages is None or not self._confirm_unsaved_changes():
            return
        source_language, target_language = languages
        self._project_io.create_from_csv(
            source_path,
            Path(destination_name),
            source_language,
            target_language,
            field_mapping,
        )

    def _import_xml(self) -> None:
        source_name, _ = QFileDialog.getOpenFileName(
            self, "Import XML", "", "XML files (*.xml)"
        )
        if not source_name:
            return
        field_mapping = self._import_mappings.ask_xml(Path(source_name))
        destination_name, _ = QFileDialog.getSaveFileName(
            self, "Create LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        if not destination_name:
            return
        mapping_description = (
            "Element text nodes; XML structure, comments, and non-translatable values are preserved"
            if field_mapping is None
            else "Element text nodes and attributes: " + ", ".join(field_mapping.attribute_names)
        )
        languages = self._ask_project_setup(
            Path(source_name), Path(destination_name), "XML", mapping_description
        )
        if languages is None or not self._confirm_unsaved_changes():
            return
        source_language, target_language = languages
        self._project_io.create_from_xml(
            Path(source_name),
            Path(destination_name),
            source_language,
            target_language,
            field_mapping,
        )

    def _open_project(self) -> None:
        path_name, _ = QFileDialog.getOpenFileName(
            self, "Open LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        if path_name:
            if not self._confirm_unsaved_changes():
                return
            self._project_io.open(Path(path_name))

    def _save_project(self) -> None:
        self._project_io.save()

    def _save_project_as(self) -> None:
        if not self._workspace.has_project:
            return
        path_name, _ = QFileDialog.getSaveFileName(
            self, "Save LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        if not path_name:
            return
        self._project_io.save(Path(path_name))

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
        self._project_io.export_json(Path(path_name))

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
        self._project_io.export_po(Path(path_name))

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
        self._project_io.export_csv(Path(path_name))

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
        self._project_io.export_xml(Path(path_name))

    def _export_all_documents(self) -> None:
        if not self._workspace.has_project or not self._confirm_export_warnings(
            "will retain source text or remain empty, depending on the file format"
        ):
            return
        directory_name = QFileDialog.getExistingDirectory(
            self, "Export all project files"
        )
        if not directory_name:
            return
        self._project_io.export_all_documents(Path(directory_name))

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

    def _select_translation_candidate(self, candidate: str) -> None:
        if self._current_entry_id is None or self._current_entry_locked or self._busy:
            return
        label = "model" if candidate == "model" else "reviewer"
        self._run_project_action(
            lambda: self._workspace.select_translation_candidate(
                self._current_entry_id or "", candidate
            ),
            f"{label.capitalize()} translation selected",
        )

    def _undo_last_translation(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        self._run_project_action(
            self._workspace.undo_last_translation,
            "Last translation operation undone",
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
            self._quality.issues_by_entry,
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
        self._filters.set_issues_only(False)
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
        if self._memory.suggestion is None:
            return
        self._translation_editor.setPlainText(self._memory.suggestion)
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

    def _translate_selected(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        entry_ids = self._selected_entry_ids()
        if not entry_ids:
            QMessageBox.information(self, "Batch translation", "Select one or more rows")
            return
        self._translation.start(entry_ids)

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
        self._translation.start(entry_ids)

    def _validate_project(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        self._validation.start()

    def _show_validation_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

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

    def _select_all_qa_entries(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        self._filters.clear()
        self._filters.set_issues_only(True)
        issue_count = self._proxy_model.rowCount()
        if not issue_count:
            self.statusBar().showMessage("No entries with QA issues", 3000)
            return
        self._table.selectAll()
        self.statusBar().showMessage(f"Selected {issue_count} entries with QA issues", 3000)

    def _retranslate_all_qa_entries(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        entry_ids = tuple(
            entry.id
            for entry in self._workspace.project.entries
            if entry.id in self._quality.issues_by_entry
            and not entry.locked
            and entry.status is not EntryStatus.APPROVED
        )
        if not entry_ids:
            QMessageBox.information(
                self,
                "Batch translation",
                "There are no editable entries with QA issues.",
            )
            return
        if QMessageBox.question(
            self,
            "Re-translate QA entries",
            f"Re-translate {len(entry_ids)} QA entries? "
            "Their current translations will be replaced.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._translation.start(entry_ids)

    def _dismiss_selected_ai_issues(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        entry_ids = tuple(
            entry_id
            for entry_id in self._selected_entry_ids()
            if any(
                issue.code is ValidationCode.AI_REVIEW
                for issue in self._quality.issues_by_entry.get(entry_id, ())
            )
        )
        if not entry_ids:
            QMessageBox.information(
                self, "AI review", "Select entries with AI review issues."
            )
            return
        if QMessageBox.question(
            self,
            "Dismiss AI review issues",
            f"Dismiss AI review issues for {len(entry_ids)} selected entries?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._run_project_action(
            lambda: self._workspace.dismiss_ai_review_issues(entry_ids),
            "Selected AI review issues dismissed",
        )

    def _review_selected(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        entry_ids = self._selected_entry_ids()
        if not entry_ids:
            QMessageBox.information(self, "AI review", "Select one or more rows")
            return
        self._review.start(entry_ids)

    def _review_all(self) -> None:
        if not self._workspace.has_project or self._busy:
            return
        entry_ids = self._workspace.reviewable_entry_ids()
        if not entry_ids:
            QMessageBox.information(
                self, "AI review", "There are no unlocked Needs review entries"
            )
            return
        self._review.start(entry_ids)

    def _review_progress(self, completed: int, total: int) -> None:
        self._progress.setRange(0, max(total, 1))
        self._progress.setValue(completed)
        self.statusBar().showMessage(f"Reviewing {completed} of {total}")

    def _show_review_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

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
            self._translation.start((self._current_entry_id,))

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
        if self._translation.cancel():
            operation = "translation"
        elif self._review.cancel():
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
        if self._busy:
            return
        settings = (
            self._workspace.project.model_settings
            if self._workspace.has_project
            else self._model_settings_profile.load()
        )
        try:
            models = self._workspace.list_models()
            if not models:
                status_message = (
                    "Connected — no models installed. Use Tools → Ollama Setup..."
                )
            elif settings.model not in models:
                status_message = (
                    f"Connected — configured model {settings.model} is not installed; "
                    "an installed model was selected"
                )
            else:
                status_message = f"Connected — {len(models)} model(s) found"
        except Exception as error:
            models = ()
            status_message = f"Unavailable — {error}"
        dialog = OllamaSettingsDialog(
            settings,
            models,
            status_message,
            self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if not self._workspace.has_project:
            self._model_settings_profile.save(dialog.model_settings())
            self.statusBar().showMessage("User model settings saved", 5000)
            return
        if dialog.save_as_default():
            self._model_settings_profile.save(dialog.model_settings())
        self._run_project_action(
            lambda: self._workspace.update_model_settings(dialog.model_settings()),
            "Ollama settings updated",
        )

    def _open_ollama_setup(self) -> None:
        if self._busy:
            return
        try:
            installed_models = self._workspace.list_models()
        except Exception:
            self._offer_ollama_installation()
            return
        configured_model = (
            self._workspace.project.model_settings.model
            if self._workspace.has_project
            else self._model_settings_profile.load().model
        )
        model, accepted = QInputDialog.getText(
            self,
            "Install Ollama model",
            "Model name to download:\n"
            f"Installed: {', '.join(installed_models) if installed_models else 'none'}",
            text=configured_model,
        )
        normalized_model = model.strip()
        if not accepted or not normalized_model:
            return
        if normalized_model in installed_models:
            QMessageBox.information(
                self, "Ollama model", f"{normalized_model} is already installed."
            )
            return
        if QMessageBox.question(
            self,
            "Install Ollama model",
            f"Download {normalized_model}? Models can require many gigabytes of disk space.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._model_pull.start(normalized_model)

    def _ensure_model_available(self, model: str, reviewer: bool = False) -> bool:
        try:
            installed_models = self._workspace.list_models()
        except Exception:
            self._offer_ollama_installation()
            return False
        if model in installed_models:
            return True
        if installed_models:
            download_choice = f"Download configured model: {model}"
            selected, accepted = QInputDialog.getItem(
                self,
                "Choose Ollama model",
                f"Configured model {model} is not installed.",
                (*installed_models, download_choice),
                0,
                False,
            )
            if not accepted:
                return False
            if selected != download_choice:
                settings = self._workspace.project.model_settings
                updated_settings = (
                    replace(settings, review_model=selected)
                    if reviewer
                    else replace(settings, model=selected)
                )
                self._workspace.update_model_settings(updated_settings)
                self._model_name.setText(updated_settings.model)
                return True
        if QMessageBox.question(
            self,
            "Ollama model is not installed",
            f"Model {model} is not installed. Download it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        ) == QMessageBox.StandardButton.Yes:
            self._model_pull.start(model)
        return False

    def _offer_ollama_installation(self) -> None:
        if QMessageBox.question(
            self,
            "Ollama is unavailable",
            "LocaForge cannot connect to Ollama. Open the official Windows installer page?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        ) == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl("https://ollama.com/download/windows"))

    def _prepare_model_pull_progress(self) -> None:
        self._cancel_button.setEnabled(False)
        self._progress.setRange(0, 0)

    def _show_model_pull_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def _open_translation_memory_editor(self) -> None:
        dialog = TranslationMemoryDialog(self._workspace, self)
        dialog.exec()
        self._memory.invalidate()

    def _show_translation_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def _show_translation_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

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
        self._model_candidate.setPlainText(entry.model_translation or "")
        self._reviewer_candidate.setPlainText(entry.reviewer_translation or "")
        self._use_model_candidate_button.setEnabled(
            entry.model_translation is not None and not entry.locked and not self._busy
        )
        self._use_reviewer_candidate_button.setEnabled(
            entry.reviewer_translation is not None and not entry.locked and not self._busy
        )
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
        self._quality.refresh_current()
        self._memory.refresh(entry.id)
        self._history.refresh(entry.id)

    def _refresh_project(self, select_first: bool = True) -> None:
        has_project = self._workspace.has_project
        selected_entry_id = self._current_entry_id
        if has_project and self._workspace.project.model_settings == ModelSettings():
            user_defaults = self._model_settings_profile.load()
            if user_defaults != ModelSettings():
                self._workspace.update_model_settings(user_defaults)
        self._memory.invalidate()
        entries = self._workspace.project.entries if has_project else []
        self._model.set_entries(entries)
        self._filters.update_documents(
            self._workspace.project.documents if has_project else ()
        )
        self._filters.update_entries(entries)
        self._project_overview.refresh()
        self._quality.refresh()
        self._glossary.refresh()
        project_actions_enabled = has_project and not self._busy
        self._import_multiple_action.setEnabled(not self._busy)
        self._import_action.setEnabled(not self._busy)
        self._import_po_action.setEnabled(not self._busy)
        self._import_csv_action.setEnabled(not self._busy)
        self._import_xml_action.setEnabled(not self._busy)
        self._open_action.setEnabled(not self._busy)
        self._save_action.setEnabled(project_actions_enabled)
        self._save_as_action.setEnabled(project_actions_enabled)
        self._undo_translation_action.setEnabled(
            project_actions_enabled and self._workspace.can_undo_last_translation()
        )
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
        self._export_all_action.setEnabled(project_actions_enabled)
        self._translate_button.setEnabled(project_actions_enabled)
        self._settings_button.setEnabled(not self._busy)
        self._ollama_setup_action.setEnabled(not self._busy)
        self._translation_memory_action.setEnabled(not self._busy)
        self._translate_all_action.setEnabled(project_actions_enabled)
        self._replace_translations_action.setEnabled(project_actions_enabled)
        self._select_qa_entries_action.setEnabled(project_actions_enabled)
        self._retranslate_qa_entries_action.setEnabled(project_actions_enabled)
        self._dismiss_selected_ai_issues_action.setEnabled(project_actions_enabled)
        self._approve_selected_action.setEnabled(project_actions_enabled)
        self._review_selected_action.setEnabled(project_actions_enabled)
        self._review_all_action.setEnabled(project_actions_enabled)
        self._reopen_selected_action.setEnabled(project_actions_enabled)
        self._lock_selected_action.setEnabled(project_actions_enabled)
        self._unlock_selected_action.setEnabled(project_actions_enabled)
        self._validate_project_action.setEnabled(project_actions_enabled)
        self._filters.set_issues_enabled(project_actions_enabled)
        self._glossary.set_enabled(project_actions_enabled)
        self._table.setEnabled(not self._busy)
        self._translation_editor.setEnabled(not self._busy)
        self._use_model_candidate_button.setEnabled(False)
        self._use_reviewer_candidate_button.setEnabled(False)
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
            if selected_entry_id is not None and self._select_visible_entry_by_id(
                selected_entry_id
            ):
                return
            if select_first and self._proxy_model.rowCount():
                self._table.selectRow(0)
            elif not select_first:
                self._table.clearSelection()
                self._table.setCurrentIndex(QModelIndex())
        else:
            self._model_name.setText("Not configured")
            self.setWindowTitle("LocaForge")

    def _refresh_project_sidebars(self) -> None:
        if not self._workspace.has_project:
            return
        self._project_overview.refresh()
        self._quality.refresh()

    def _clear_editor(self) -> None:
        self._current_entry_id = None
        self._current_entry_locked = False
        self._current_entry_max_length = None
        self._source_editor.clear()
        self._translation_editor.clear()
        self._model_candidate.clear()
        self._reviewer_candidate.clear()
        self._use_model_candidate_button.setEnabled(False)
        self._use_reviewer_candidate_button.setEnabled(False)
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
        self._history.clear()
        self._memory.clear()

    def _refresh_translation_length(self) -> None:
        self._translation_length.setText(
            format_translation_length(
                len(self._translation_editor.toPlainText()),
                self._current_entry_max_length,
            )
        )

    def _select_entry_by_id(self, entry_id: str) -> None:
        self._filters.clear_text_and_statuses()
        self._select_visible_entry_by_id(entry_id)

    def _select_visible_entry_by_id(self, entry_id: str) -> bool:
        for row, entry in enumerate(self._workspace.project.entries):
            if entry.id != entry_id:
                continue
            proxy_index = self._proxy_model.mapFromSource(self._model.index(row, 0))
            if proxy_index.isValid():
                self._table.selectRow(proxy_index.row())
                self._table.scrollTo(proxy_index)
                return True
            return False
        return False

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
        self._memory.invalidate()
        self._model.update_entry(entry)
        entries = self._workspace.project.entries if self._workspace.has_project else ()
        self._filters.update_entries(entries)
        dirty_mark = " *" if self._workspace.project.dirty else ""
        self.setWindowTitle(f"LocaForge — {self._workspace.project.name}{dirty_mark}")
        self._summary_refresh_timer.start()
        if self._current_entry_id == entry.id:
            self._memory.refresh(entry.id)
        self._sync_autosave()
        self.statusBar().showMessage(success_message, 5000)
        return True

    def _show_recent_project_info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

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
        if self._translation.is_running:
            QMessageBox.warning(
                self,
                "Translation in progress",
                "Wait for the current translation request to finish before closing LocaForge.",
            )
            event.ignore()
            return
        if self._review.is_running:
            QMessageBox.warning(
                self,
                "AI review in progress",
                "Wait for the current AI review request to finish before closing LocaForge.",
            )
            event.ignore()
            return
        if self._validation.is_running:
            QMessageBox.warning(
                self,
                "Validation in progress",
                "Wait for project validation to finish before closing LocaForge.",
            )
            event.ignore()
            return
        if self._model_pull.is_running:
            QMessageBox.warning(
                self,
                "Model download in progress",
                "Wait for the Ollama model download to finish before closing LocaForge.",
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

    def _ask_project_setup(
        self,
        source_path: Path,
        destination_path: Path,
        source_format: str,
        mapping_description: str,
    ) -> tuple[str, str] | None:
        dialog = ProjectSetupDialog(
            source_path,
            destination_path,
            source_format,
            mapping_description,
            self,
        )
        if dialog.exec() != ProjectSetupDialog.DialogCode.Accepted:
            return None
        return dialog.language_pair()
