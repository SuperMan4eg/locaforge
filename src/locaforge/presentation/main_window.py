"""Main PySide6 window for the desktop MVP."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

from PySide6.QtCore import QModelIndex, QPoint, QSettings, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from locaforge.application.dto.project import DocumentRefreshPreview, ExportPreflight
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.entry import TranslationEntry
from locaforge.infrastructure.llm.ollama_client import OllamaClient
from locaforge.presentation.application_appearance_renderer import (
    ApplicationAppearanceRenderer,
)
from locaforge.presentation.application_settings import (
    ApplicationSettings,
    ApplicationSettingsStore,
)
from locaforge.presentation.application_settings_controller import (
    ApplicationSettingsController,
)
from locaforge.presentation.application_settings_dialog import ApplicationSettingsDialog
from locaforge.presentation.autosave_controller import AutosaveController
from locaforge.presentation.autosave_policy_controller import AutosavePolicyController
from locaforge.presentation.bulk_entry_operations_controller import (
    BulkEntryOperationsController,
)
from locaforge.presentation.edit_actions import build_edit_actions
from locaforge.presentation.entry_action_runner import EntryActionRunner
from locaforge.presentation.file_actions import build_file_actions
from locaforge.presentation.glossary_controller import GlossaryController
from locaforge.presentation.history_controller import HistoryController
from locaforge.presentation.import_files_preview_dialog import ImportFilesPreviewDialog
from locaforge.presentation.import_mapping_controller import ImportMappingController
from locaforge.presentation.json_import_profiles import (
    JsonImportProfileStore,
)
from locaforge.presentation.localization import LocalizationManager
from locaforge.presentation.log_viewer import LogViewerController
from locaforge.presentation.model_availability_controller import ModelAvailabilityController
from locaforge.presentation.model_pull_controller import ModelPullController
from locaforge.presentation.navigation_actions import build_navigation_actions
from locaforge.presentation.new_project_dialog import NewProjectDialog
from locaforge.presentation.operation_progress_controller import OperationProgressController
from locaforge.presentation.project_action_runner import ProjectActionRunner
from locaforge.presentation.project_action_state import (
    ProjectActionStateRenderer,
)
from locaforge.presentation.project_configuration_controller import (
    ProjectConfiguration,
    ProjectConfigurationController,
)
from locaforge.presentation.project_creation_import_controller import (
    ProjectCreationImportController,
)
from locaforge.presentation.project_document_operations_controller import (
    ProjectDocumentOperationsController,
)
from locaforge.presentation.project_document_view_controller import (
    ProjectDocumentViewController,
)
from locaforge.presentation.project_explorer_controller import ProjectExplorerController
from locaforge.presentation.project_export_controller import ProjectExportController
from locaforge.presentation.project_file_import_controller import ProjectFileImportController
from locaforge.presentation.project_information_controller import ProjectInformationController
from locaforge.presentation.project_io_controller import ProjectIoController
from locaforge.presentation.project_lifecycle_controller import ProjectLifecycleController
from locaforge.presentation.project_refresh import ProjectRefreshService
from locaforge.presentation.project_setup_dialog import ProjectSetupDialog
from locaforge.presentation.project_workspace_widgets import (
    build_project_workspace_widgets,
)
from locaforge.presentation.qa_entry_operations_controller import (
    QaEntryOperationsController,
)
from locaforge.presentation.quality_panel_controller import QualityPanelController
from locaforge.presentation.recent_projects import RecentProjectsStore
from locaforge.presentation.recent_projects_controller import RecentProjectsController
from locaforge.presentation.review_actions import build_review_actions
from locaforge.presentation.review_controller import ReviewController
from locaforge.presentation.sidebar_widgets import build_sidebar_widgets
from locaforge.presentation.tools_actions import build_tools_actions
from locaforge.presentation.translation_controller import TranslationController
from locaforge.presentation.translation_editor_state import TranslationEditorState
from locaforge.presentation.translation_entry_controller import TranslationEntryController
from locaforge.presentation.translation_filter_controller import TranslationFilterController
from locaforge.presentation.translation_filter_proxy import TranslationFilterProxyModel
from locaforge.presentation.translation_length import format_translation_length
from locaforge.presentation.translation_memory_controller import (
    TranslationMemoryController,
)
from locaforge.presentation.translation_memory_dialog import TranslationMemoryDialog
from locaforge.presentation.translation_navigation_controller import (
    TranslationNavigationController,
)
from locaforge.presentation.translation_table_model import TranslationTableModel
from locaforge.presentation.translation_tools_controller import TranslationToolsController
from locaforge.presentation.translation_workspace_widgets import (
    build_translation_workspace_widgets,
)
from locaforge.presentation.validation_controller import ValidationController
from locaforge.presentation.window_close_controller import (
    UnsavedChangesDecision,
    WindowCloseController,
)
from locaforge.presentation.window_layout import WindowLayoutStore
from locaforge.presentation.window_layout_controller import WindowLayoutController

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        workspace: ProjectWorkspace,
        layout_store: WindowLayoutStore | None = None,
        recent_projects: RecentProjectsStore | None = None,
        application_settings: ApplicationSettingsStore | None = None,
        localization: LocalizationManager | None = None,
    ) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self._workspace = workspace
        self._project_refresh = ProjectRefreshService(workspace)
        self._layout_store = layout_store or WindowLayoutStore(QSettings())
        self._recent_projects = recent_projects or RecentProjectsStore(QSettings())
        self._application_settings_store = application_settings or ApplicationSettingsStore(
            QSettings()
        )
        self._application_settings = self._application_settings_store.load()
        self._localization = localization
        if self._localization is not None:
            application = cast(QApplication | None, QApplication.instance())
            if application is not None:
                self._localization.install(application)
            self._localization.languageChanged.connect(self.retranslate)
        else:
            application = cast(QApplication | None, QApplication.instance())
            if application is not None:
                LocalizationManager.uninstall_active(application)
        self._workspace.set_global_model_settings(self._application_settings.model_settings)
        self._workspace.set_llm_client(OllamaClient(self._application_settings.ollama_server_url))
        self._recent: RecentProjectsController
        self._json_import_profiles = JsonImportProfileStore(QSettings())
        self._import_mappings = ImportMappingController(workspace, self._json_import_profiles, self)
        self._project_io = ProjectIoController(
            workspace,
            self._run_project_action,
            lambda: self._recent.remember_current(),
        )
        self._project_creation_import = ProjectCreationImportController(
            self._project_io,
            choose_source=self._choose_project_import_source,
            choose_destination=self._choose_project_import_destination,
            ask_project_setup=self._ask_project_setup,
            confirm_unsaved_changes=self._confirm_unsaved_changes,
            ask_json_mapping=self._import_mappings.ask_json,
            ask_csv_mapping=self._import_mappings.ask_csv,
            ask_xml_mapping=self._import_mappings.ask_xml,
        )
        self._project_configuration = ProjectConfigurationController(
            self._workspace,
            self._project_io,
            confirm_unsaved_changes=self._confirm_unsaved_changes,
            ask_new_configuration=self._ask_new_project_configuration,
            choose_destination=self._choose_new_project_destination,
            ask_existing_configuration=self._ask_existing_project_configuration,
            run_action=self._run_project_action,
        )
        self._model = TranslationTableModel(self)
        self._proxy_model = TranslationFilterProxyModel()
        self._proxy_model.setSourceModel(self._model)
        self._current_entry_id: str | None = None
        self._current_entry_locked = False
        self._current_entry_max_length: int | None = None
        self._busy = False

        self._filters = TranslationFilterController(self._model, self._proxy_model, self)
        self._translation_ui = build_translation_workspace_widgets(
            self,
            table_model=self._proxy_model,
            add_filters=self._filters.add_to_layout,
            current_row_changed=self._on_current_row_changed,
            select_candidate=self._select_translation_candidate,
            refresh_translation_length=self._refresh_translation_length,
            dismiss_ai_issue=self._dismiss_ai_review_issue,
            retranslate_current=self._retranslate_current_entry,
            apply_to_matches=self._apply_translation_to_matches,
            copy_source=self._copy_source_to_translation,
            apply_translation=self._apply_translation,
            toggle_approval=self._toggle_entry_approval,
            set_locked=self._set_entry_locked,
            translate_selected=self._translate_selected,
            cancel_translation=self._cancel_translation,
        )
        self._appearance = ApplicationAppearanceRenderer(
            self,
            (
                self._translation_ui.source_editor,
                self._translation_ui.translation_editor,
                self._translation_ui.model_candidate,
                self._translation_ui.reviewer_candidate,
                self._translation_ui.table,
            ),
        )
        self._summary_refresh_timer = QTimer(self)
        self._summary_refresh_timer.setSingleShot(True)
        self._summary_refresh_timer.setInterval(500)
        self._summary_refresh_timer.timeout.connect(self._refresh_project_sidebars)
        self._project_ui = build_project_workspace_widgets(
            self,
            add_files=self._import_multiple_files,
            add_folder=self._import_folder,
            export_selected=self._export_selected_documents,
            remove_selected=self._remove_selected_documents,
            refresh_selected=self._refresh_selected_documents,
            edit_settings=self._edit_project_settings,
            preview_context=self._preview_project_context,
            show_context_menu=self._show_project_context_menu,
            open_document=self._open_project_document,
        )
        self._workspace_tabs = QTabWidget(self)
        self._workspace_tabs.addTab(self._translation_ui.content, "Translations")
        self._workspace_tabs.addTab(self._project_ui.content, "Project")
        self.setCentralWidget(self._workspace_tabs)

        self._sidebars = build_sidebar_widgets(
            self,
            copy_diagnostics=self._copy_diagnostics,
        )

        self._build_menu()

        self._autosave = AutosaveController(self._workspace.autosave, parent=self)
        self._autosave.set_delay(self._application_settings.autosave_delay_seconds * 1000)
        self._autosave.saved.connect(self._autosave_succeeded)
        self._autosave.failed.connect(self._autosave_failed)
        self._autosave_policy = AutosavePolicyController(
            self._workspace,
            application_settings=lambda: self._application_settings,
            schedule=self._autosave.schedule,
            cancel=self._autosave.cancel,
            refresh_project=self._refresh_project,
            show_status=lambda message, timeout: self.statusBar().showMessage(message, timeout),
            show_failure=self._show_autosave_failure,
        )
        self._operation_progress = OperationProgressController(
            set_busy_state=self._set_busy_state,
            cancel_autosave=self._autosave.cancel,
            set_progress_visible=self._translation_ui.progress.setVisible,
            set_cancel_visible=self._translation_ui.cancel_button.setVisible,
            set_cancel_enabled=self._translation_ui.cancel_button.setEnabled,
            set_progress_range=self._translation_ui.progress.setRange,
            set_progress_value=self._translation_ui.progress.setValue,
            refresh_project=self._refresh_project,
            show_status=self.statusBar().showMessage,
        )
        self._project_actions = ProjectActionRunner(
            is_busy=lambda: self._busy,
            refresh_project=self._refresh_project,
            sync_autosave=self._sync_autosave,
            show_status=lambda message, timeout: self.statusBar().showMessage(message, timeout),
            show_error=self._show_project_action_error,
        )
        self._application_settings_controller = ApplicationSettingsController(
            self._workspace,
            self._application_settings_store,
            set_current_settings=self._set_current_application_settings,
            configure_ollama_server=self._configure_ollama_server,
            set_locale=(
                self._localization.set_locale if self._localization is not None else None
            ),
            retranslate=self.retranslate,
            set_autosave_delay=self._autosave.set_delay,
            apply_visual_settings=self._apply_application_settings,
            sync_autosave=self._sync_autosave,
            show_saved=self._show_application_settings_saved,
        )
        self._review = ReviewController(
            workspace=self._workspace,
            ensure_model=self._ensure_model_available,
            set_busy=lambda busy, refresh: self._set_busy(busy, refresh),
            refresh_project=lambda select_first: self._refresh_project(select_first),
            sync_autosave=self._sync_autosave,
            show_status=lambda message, timeout: self.statusBar().showMessage(message, timeout),
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
            show_status=lambda message, timeout: self.statusBar().showMessage(message, timeout),
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
            disable_cancel=lambda: self._translation_ui.cancel_button.setEnabled(False),
            show_status=lambda message, timeout: self.statusBar().showMessage(message, timeout),
            show_error=self._show_validation_error,
            parent=self,
        )
        self._model_pull = ModelPullController(
            workspace=self._workspace,
            set_busy=lambda busy, refresh: self._set_busy(busy, refresh),
            prepare_progress=self._prepare_model_pull_progress,
            show_status=lambda message, timeout: self.statusBar().showMessage(message, timeout),
            show_error=self._show_model_pull_error,
            parent=self,
        )
        self._model_availability = ModelAvailabilityController(
            self._workspace,
            choose_model=self._choose_available_model,
            confirm_download=self._confirm_model_download,
            offer_ollama_installation=self._offer_ollama_installation,
            start_model_pull=self._model_pull.start,
            set_displayed_model=self._translation_ui.model_name.setText,
        )
        self._memory = TranslationMemoryController(
            workspace=self._workspace,
            suggestions=self._sidebars.translation_memory_list,
            apply_button=self._sidebars.apply_memory_button,
            can_apply=lambda: not self._current_entry_locked and not self._busy,
            apply_suggestion=self._apply_memory_suggestion,
            parent=self,
        )
        self._entry_actions = EntryActionRunner(
            self._workspace,
            is_busy=lambda: self._busy,
            current_entry_id=lambda: self._current_entry_id,
            invalidate_memory=self._memory.invalidate,
            update_entry=self._model.update_entry,
            update_filter_entries=self._filters.update_entries,
            update_project_title=self._update_project_window_title,
            schedule_summary_refresh=self._summary_refresh_timer.start,
            refresh_memory=self._memory.refresh,
            sync_autosave=self._sync_autosave,
            show_status=lambda message, timeout: self.statusBar().showMessage(message, timeout),
            show_error=self._show_project_action_error,
        )
        self._glossary = GlossaryController(
            workspace=self._workspace,
            terms=self._sidebars.glossary_list,
            add_button=self._sidebars.glossary_add_button,
            remove_button=self._sidebars.glossary_remove_button,
            import_button=self._sidebars.glossary_import_button,
            export_button=self._sidebars.glossary_export_button,
            run_action=self._run_project_action,
            source_text=self._translation_ui.source_editor.toPlainText,
            translation_text=self._translation_ui.translation_editor.toPlainText,
            is_busy=lambda: self._busy,
            parent=self,
        )
        self._history = HistoryController(
            workspace=self._workspace,
            revisions=self._sidebars.history_list,
            operations=self._sidebars.operation_history_list,
            restore_button=self._sidebars.restore_history_button,
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
            self._workspace,
            self._project_ui.explorer,
            self._project_documents_selected,
            self,
            file_tree=self._project_ui.file_tree,
        )
        self._project_documents = ProjectDocumentViewController(
            self._workspace,
            self._project_overview,
            self._project_ui,
            set_document_filter=self._filters.set_document_ids,
            is_busy=lambda: self._busy,
            show_translations=self._show_project_document_translations,
            open_source_path=self._open_source_path,
            refresh_selected=self._refresh_selected_documents,
            export_selected=self._export_selected_documents,
            remove_selected=self._remove_selected_documents,
            add_files=self._import_multiple_files,
            add_folder=self._import_folder,
            edit_settings=self._edit_project_settings,
            parent=self,
        )
        self._project_document_operations = ProjectDocumentOperationsController(
            self._workspace,
            self._project_overview,
            run_action=self._run_project_action,
            confirm_remove=self._confirm_remove_documents,
            confirm_refresh=self._confirm_document_refresh,
            show_refresh_error=self._show_document_refresh_error,
            clear_selection=self._project_ui.file_tree.clearSelection,
            parent=self,
        )
        self._project_export = ProjectExportController(
            self._workspace,
            self._project_io,
            selected_document_ids=self._project_overview.selected_document_ids,
            choose_save_file=self._choose_export_file,
            choose_directory=self._choose_export_directory,
            warnings_enabled=lambda: self._application_settings.confirm_export_warnings,
            confirm_warnings=self._confirm_export_warnings,
            show_no_selection=self._show_no_export_selection,
        )
        self._project_file_import = ProjectFileImportController(
            self._workspace,
            self._project_io,
            choose_files=self._choose_import_files,
            choose_folder=self._choose_import_folder,
            preview_import=self._preview_file_import,
            ask_json_mapping=self._import_mappings.ask_json,
            ask_csv_mapping=self._import_mappings.ask_csv,
            ask_xml_mapping=self._import_mappings.ask_xml,
            show_information=self._show_information,
        )
        self._project_lifecycle = ProjectLifecycleController(
            self._workspace,
            self._project_io,
            choose_open_path=self._choose_open_project_path,
            choose_save_path=self._choose_save_project_path,
            confirm_unsaved_changes=self._confirm_unsaved_changes,
            confirm_recovery=self._confirm_project_recovery,
            show_open_error=self._show_project_open_error,
            project_opened=self._project_opened,
        )
        self._project_information = ProjectInformationController(
            self._workspace,
            application_settings=lambda: self._application_settings,
            show_information=self._show_information,
            copy_text=self._copy_to_clipboard,
            diagnostics_copied=self._show_diagnostics_copied,
        )
        self._project_ui.file_search.textChanged.connect(self._filter_project_files)
        self._quality = QualityPanelController(
            workspace=self._workspace,
            category_filter=self._sidebars.validation_filter,
            issue_list=self._sidebars.validation_list,
            current_issues=self._translation_ui.current_issues,
            dismiss_ai_button=self._translation_ui.dismiss_ai_issue_button,
            retranslate_button=self._translation_ui.retranslate_button,
            apply_matching_button=self._translation_ui.apply_matching_button,
            table_filters=self._filters,
            current_entry_id=lambda: self._current_entry_id,
            is_busy=lambda: self._busy,
            select_entry=self._select_entry_by_id,
            parent=self,
        )
        self._navigation = TranslationNavigationController(
            self._workspace,
            current_entry_id=lambda: self._current_entry_id,
            is_busy=lambda: self._busy,
            current_row=self._current_translation_row,
            row_count=self._proxy_model.rowCount,
            select_row=self._select_translation_row,
            issue_entry_ids=lambda: self._quality.issues_by_entry,
            select_entry=self._select_entry_by_id,
            clear_issues_only=lambda: self._filters.set_issues_only(False),
            show_status=lambda message, timeout: self.statusBar().showMessage(message, timeout),
            apply_translation=self._apply_translation,
        )
        self._entry_operations = TranslationEntryController(
            self._workspace,
            current_entry_id=lambda: self._current_entry_id,
            current_entry_locked=lambda: self._current_entry_locked,
            is_busy=lambda: self._busy,
            source_text=self._translation_ui.source_editor.toPlainText,
            translation_text=self._translation_ui.translation_editor.toPlainText,
            set_translation_text=self._translation_ui.translation_editor.setPlainText,
            set_lock_checked=self._translation_ui.lock_button.setChecked,
            run_action=self._run_project_action,
            show_status=lambda message, timeout: self.statusBar().showMessage(message, timeout),
            show_warning=self._show_entry_operation_warning,
            confirm_matching_apply=self._confirm_matching_translation_apply,
        )
        self._bulk_entries = BulkEntryOperationsController(
            self._workspace,
            selected_entry_ids=self._selected_entry_ids,
            current_entry_id=lambda: self._current_entry_id,
            current_entry_locked=lambda: self._current_entry_locked,
            is_busy=lambda: self._busy,
            start_translation=self._translation.start,
            start_review=self._review.start,
            run_action=self._run_project_action,
            show_information=self._show_information,
        )
        self._qa_entries = QaEntryOperationsController(
            self._workspace,
            is_busy=lambda: self._busy,
            issues_by_entry=lambda: self._quality.issues_by_entry,
            selected_entry_ids=self._selected_entry_ids,
            clear_filters=self._filters.clear,
            show_issues_only=lambda: self._filters.set_issues_only(True),
            visible_row_count=self._proxy_model.rowCount,
            select_all_visible=self._translation_ui.table.selectAll,
            start_translation=self._translation.start,
            run_action=self._run_project_action,
            show_status=lambda message, timeout: self.statusBar().showMessage(message, timeout),
            show_information=self._show_information,
            confirm_retranslation=self._confirm_qa_retranslation,
            confirm_dismissal=self._confirm_ai_issue_dismissal,
        )
        self._translation_tools = TranslationToolsController(
            self._workspace,
            current_entry_id=lambda: self._current_entry_id,
            is_busy=lambda: self._busy,
            start_validation=self._validation.start,
            ask_replacement=self._ask_translation_replacement,
            confirm_replacement=self._confirm_translation_replacement,
            run_action=self._run_project_action,
            cancel_translation=self._translation.cancel,
            cancel_review=self._review.cancel,
            disable_cancel=lambda: self._translation_ui.cancel_button.setEnabled(False),
            show_status=self.statusBar().showMessage,
        )
        self._log_viewer = LogViewerController(parent=self)
        self._log_viewer.message_logged.connect(self._sidebars.log_view.appendPlainText)
        self._log_viewer.attach()
        logger.info("Log viewer attached")
        self._window_close = WindowCloseController(
            self._workspace,
            translation_running=lambda: self._translation.is_running,
            review_running=lambda: self._review.is_running,
            validation_running=lambda: self._validation.is_running,
            model_pull_running=lambda: self._model_pull.is_running,
            ask_unsaved_changes=self._ask_unsaved_changes,
            cancel_autosave=self._autosave.cancel,
            wait_for_autosave=self._autosave.wait_for_completion,
            persist_layout=self._persist_window_layout,
            detach_log_viewer=self._log_viewer.detach,
            show_warning=self._show_close_warning,
            show_save_error=self._show_unsaved_save_error,
        )

        self._project_action_state = ProjectActionStateRenderer(
            edit_actions=self._edit_actions,
            idle_targets=(
                self._file_actions.new_project,
                self._file_actions.open_project,
                self._tools_actions.translation_memory,
                self._translation_ui.table,
                self._translation_ui.translation_editor,
            ),
            project_targets=(
                self._file_actions.import_files,
                self._file_actions.import_folder,
                self._project_ui.add_files_button,
                self._project_ui.add_folder_button,
                self._project_ui.settings_button,
                self._project_ui.context_button,
                self._file_actions.save,
                self._file_actions.save_as,
                self._file_actions.export_all,
                self._translation_ui.translate_button,
                self._tools_actions.translate_all,
                self._tools_actions.replace_translations,
                self._tools_actions.validate_project,
                self._review_actions.select_qa_entries,
                self._review_actions.retranslate_qa_entries,
                self._review_actions.dismiss_selected_ai_issues,
                self._review_actions.approve_selected,
                self._review_actions.review_selected,
                self._review_actions.review_all,
                self._review_actions.reopen_selected,
                self._review_actions.lock_selected,
                self._review_actions.unlock_selected,
            ),
            selected_document_targets=(
                self._project_ui.export_selected_button,
                self._project_ui.remove_selected_button,
                self._project_ui.refresh_selected_button,
                self._file_actions.export_selected,
            ),
            format_export_targets={
                "json": self._file_actions.export_json,
                "po": self._file_actions.export_po,
                "csv": self._file_actions.export_csv,
                "xml": self._file_actions.export_xml,
            },
            reset_disabled_targets=(
                self._translation_ui.use_model_candidate_button,
                self._translation_ui.use_reviewer_candidate_button,
                self._translation_ui.approve_button,
                self._translation_ui.lock_button,
                self._sidebars.restore_history_button,
                self._sidebars.apply_memory_button,
                self._translation_ui.copy_source_button,
                self._translation_ui.apply_button,
            ),
            set_issues_enabled=self._filters.set_issues_enabled,
            set_glossary_enabled=self._glossary.set_enabled,
        )

        self.resize(1200, 720)
        self._default_window_geometry = self.saveGeometry()
        self._default_window_state = self.saveState()
        self._window_layout = WindowLayoutController(
            self._layout_store,
            self._default_window_geometry,
            self._default_window_state,
            save_geometry=self.saveGeometry,
            save_state=self.saveState,
            restore_geometry=self.restoreGeometry,
            restore_state=self.restoreState,
            show_status=lambda message, timeout: self.statusBar().showMessage(message, timeout),
        )
        self._apply_application_settings()
        self._restore_window_layout()
        self.statusBar().showMessage("Ready")
        self.retranslate()
        self._refresh_project()

    def _tr(self, key: str, english: str) -> str:
        """Translate a UI label without ever exposing a message key to users."""

        if self._localization is None:
            return english
        translated = self._localization.translate(key)
        return english if translated == "Translation unavailable" else translated

    def retranslate(self, _locale: str | None = None) -> None:
        """Refresh labels owned by the main window after ``languageChanged``."""

        self._translation_ui.translate_button.setText(
            self._tr("main.translate_selected", "Translate selected")
        )
        self._translation_ui.cancel_button.setText(self._tr("main.cancel", "Cancel"))
        self._translation_ui.apply_button.setText(
            self._tr("main.apply_translation", "Apply translation")
        )
        self._translation_ui.copy_source_button.setText(self._tr("main.copy_source", "Copy source"))
        self._translation_ui.retranslate_button.setText(
            self._tr("main.retranslate", "Re-translate")
        )
        self._project_ui.file_search.setPlaceholderText(
            self._tr("main.search_project_files", "Search project files...")
        )
        self._workspace_tabs.setTabText(0, self._tr("main.translations", "Translations"))
        self._workspace_tabs.setTabText(1, self._tr("main.project", "Project"))
        self._edit_actions.application_settings.setText(
            self._tr("main.settings", "Settings...")
        )
        self._sidebars.copy_diagnostics_button.setText(
            self._tr("ui.copy_diagnostics", "Copy diagnostics")
        )
        self._refresh_project()
        if self._localization is not None:
            self._localization.localize_widget(self)

    def _build_menu(self) -> None:
        self._file_actions = build_file_actions(
            self,
            new_project=self._new_project,
            open_project=self._open_project,
            import_files=self._import_multiple_files,
            import_folder=self._import_folder,
            save=self._save_project,
            save_as=self._save_project_as,
            export_selected=self._export_selected_documents,
            export_all=self._export_all_documents,
            export_json=self._export_json,
            export_po=self._export_po,
            export_csv=self._export_csv,
            export_xml=self._export_xml,
        )
        self._recent = RecentProjectsController(
            workspace=self._workspace,
            store=self._recent_projects,
            menu=self._file_actions.recent_projects_menu,
            run_action=self._run_project_action,
            confirm_unsaved=self._confirm_unsaved_changes,
            show_info=self._show_recent_project_info,
            parent=self,
        )
        self._recent.refresh()

        self._edit_actions = build_edit_actions(
            self,
            undo=self._undo_last_translation,
            redo=self._redo_last_translation,
            open_application_settings=self._open_application_settings,
        )

        review = build_review_actions(
            self,
            select_qa_entries=self._select_all_qa_entries,
            retranslate_qa_entries=self._retranslate_all_qa_entries,
            dismiss_selected_ai_issues=self._dismiss_selected_ai_issues,
            review_selected=self._review_selected,
            review_all=self._review_all,
            approve_selected=self._approve_selected,
            reopen_selected=self._reopen_selected,
            lock_selected=self._lock_selected,
            unlock_selected=self._unlock_selected,
        )
        self._review_actions = review

        self._tools_actions = build_tools_actions(
            self,
            open_translation_memory=self._open_translation_memory_editor,
            translate_all=self._translate_all_untranslated,
            replace_translations=self._replace_translations,
            validate_project=self._validate_project,
            apply_translation=self._apply_translation,
            apply_and_next=self._apply_and_select_next,
        )

        navigation = build_navigation_actions(
            self,
            select_relative_entry=self._select_relative_entry,
            select_relative_issue=self._select_relative_issue,
            select_next_actionable_entry=self._select_next_actionable_entry,
            focus_search=self._focus_active_search,
            clear_filters=self._filters.clear,
            select_all_visible=self._select_all_visible,
            clear_project_selection=self._clear_project_filter_or_selection,
        )
        self._navigation_actions = navigation

        view_menu = self.menuBar().addMenu("&View")
        self._reset_layout_action = QAction("Reset layout", self)
        self._reset_layout_action.triggered.connect(self._reset_window_layout)
        view_menu.addAction(self._reset_layout_action)

    def _focus_active_search(self) -> None:
        if self._workspace_tabs.currentIndex() == 1:
            self._project_ui.file_search.setFocus()
            self._project_ui.file_search.selectAll()
        else:
            self._filters.focus_search()

    def _select_all_visible(self) -> None:
        if self._workspace_tabs.currentIndex() == 1:
            self._project_overview.select_visible_documents()
        else:
            self._translation_ui.table.selectAll()

    def _clear_project_filter_or_selection(self) -> None:
        if self._workspace_tabs.currentIndex() != 1:
            return
        if self._project_ui.file_search.text():
            self._project_ui.file_search.clear()
        else:
            self._project_ui.file_tree.clearSelection()

    def _import_multiple_files(self) -> None:
        self._project_file_import.add_files()

    def _choose_import_files(self) -> tuple[Path, ...]:
        source_names, _ = QFileDialog.getOpenFileNames(
            self,
            "Import localization files",
            "",
            "Localization files (*.json *.csv *.tsv *.po *.xml)",
        )
        return tuple(Path(name) for name in source_names)

    def _import_folder(self) -> None:
        self._project_file_import.add_folder()

    def _choose_import_folder(self) -> Path | None:
        directory_name = QFileDialog.getExistingDirectory(self, "Add localization folder")
        return Path(directory_name) if directory_name else None

    def _preview_file_import(
        self,
        source_paths: tuple[Path, ...],
        document_paths: dict[Path, str],
        existing_paths: tuple[str, ...],
    ) -> Mapping[Path, str] | None:
        preview = ImportFilesPreviewDialog(
            source_paths,
            document_paths,
            existing_paths,
            self,
        )
        if preview.exec() != QDialog.DialogCode.Accepted:
            return None
        return preview.project_paths()

    def _show_information(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._workspace.has_project and event.mimeData().hasUrls():
            local_paths = [url.toLocalFile() for url in event.mimeData().urls()]
            if any(local_paths):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = tuple(
            Path(local_path)
            for url in event.mimeData().urls()
            for local_path in (url.toLocalFile(),)
            if local_path
        )
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        self._project_file_import.import_paths(paths)

    def _new_project(self) -> None:
        self._project_configuration.new_project()

    def _ask_new_project_configuration(self) -> ProjectConfiguration | None:
        dialog = NewProjectDialog(
            self,
            default_languages=(
                self._application_settings.default_source_language,
                self._application_settings.default_target_language,
            ),
            profile_generator=self._workspace.generate_project_profile,
            allow_online_lookup=self._application_settings.allow_online_project_lookup,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        name, source_language, target_language, profile = dialog.project_values()
        return ProjectConfiguration(name, source_language, target_language, profile)

    def _choose_new_project_destination(self, name: str) -> Path | None:
        destination_name, _ = QFileDialog.getSaveFileName(
            self,
            "Create LocaForge project",
            f"{name}.lfproj",
            "LocaForge projects (*.lfproj)",
        )
        return Path(destination_name) if destination_name else None

    def _edit_project_settings(self) -> None:
        self._project_configuration.edit_project_settings()

    def _ask_existing_project_configuration(
        self, available_models: Sequence[str]
    ) -> ProjectConfiguration | None:
        dialog = NewProjectDialog(
            self,
            self._workspace.project,
            profile_generator=self._workspace.generate_project_profile,
            allow_online_lookup=self._application_settings.allow_online_project_lookup,
            global_model_settings=self._application_settings.model_settings,
            available_models=available_models,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        name, source_language, target_language, profile = dialog.project_values()
        return ProjectConfiguration(
            name,
            source_language,
            target_language,
            profile,
            dialog.model_settings_override.isChecked(),
            dialog.project_model_settings(),
        )

    def _preview_project_context(self) -> None:
        self._project_information.preview_project_context()

    def _import_json(self) -> None:
        self._project_creation_import.import_json()

    def _import_po(self) -> None:
        self._project_creation_import.import_po()

    def _import_csv(self) -> None:
        self._project_creation_import.import_csv()

    def _import_xml(self) -> None:
        self._project_creation_import.import_xml()

    def _choose_project_import_source(self, title: str, file_filter: str) -> Path | None:
        source_name, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        return Path(source_name) if source_name else None

    def _choose_project_import_destination(self) -> Path | None:
        destination_name, _ = QFileDialog.getSaveFileName(
            self, "Create LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        return Path(destination_name) if destination_name else None

    def _open_project(self) -> None:
        self._project_lifecycle.open_project()

    def _choose_open_project_path(self) -> Path | None:
        path_name, _ = QFileDialog.getOpenFileName(
            self, "Open LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        return Path(path_name) if path_name else None

    def _confirm_project_recovery(self, error: Exception, backup_path: Path) -> bool:
        return QMessageBox.question(
            self,
            "Recover project from backup?",
            f"The project could not be opened:\n{error}\n\n"
            f"A backup is available:\n{backup_path}\n\n"
            "Open it as an unsaved recovery copy? The damaged file will not be changed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        ) == QMessageBox.StandardButton.Yes

    def _show_project_open_error(self, message: str) -> None:
        QMessageBox.critical(self, "Cannot open project", message)

    def _project_opened(self) -> None:
        self._recent.remember_current()
        self._refresh_project()
        self.statusBar().showMessage("Project opened", 5000)

    def _save_project(self) -> None:
        self._project_lifecycle.save_project()

    def _save_project_as(self) -> None:
        self._project_lifecycle.save_project_as()

    def _choose_save_project_path(self) -> Path | None:
        path_name, _ = QFileDialog.getSaveFileName(
            self, "Save LocaForge project", "", "LocaForge projects (*.lfproj)"
        )
        return Path(path_name) if path_name else None

    def _export_json(self) -> None:
        self._project_export.export_json()

    def _export_po(self) -> None:
        self._project_export.export_po()

    def _export_csv(self) -> None:
        self._project_export.export_csv()

    def _export_xml(self) -> None:
        self._project_export.export_xml()

    def _export_all_documents(self) -> None:
        self._project_export.export_all_documents()

    def _export_selected_documents(self) -> None:
        self._project_export.export_selected_documents()

    def _project_documents_selected(self, document_ids: frozenset[str]) -> None:
        self._project_documents.selection_changed(document_ids)

    def _filter_project_files(self, text: str) -> None:
        self._project_documents.filter_files(text)

    def _update_project_file_count(self, selected_ids: frozenset[str] | None = None) -> None:
        self._project_documents.update_count(selected_ids)

    def _open_project_document(self, document_id: object) -> None:
        self._project_documents.open_document(document_id)

    def _show_project_document_translations(self) -> None:
        self._workspace_tabs.setCurrentIndex(0)
        if self._proxy_model.rowCount():
            self._translation_ui.table.setCurrentIndex(self._proxy_model.index(0, 0))

    def _show_project_context_menu(self, position: QPoint) -> None:
        self._project_documents.show_context_menu(position)

    def _refresh_project_file_details(self, document_ids: frozenset[str]) -> None:
        self._project_documents.refresh_details(document_ids)

    def _open_source_path(self, source: Path) -> None:
        location = source.parent if source.suffix else source
        if not location.exists():
            QMessageBox.warning(
                self,
                "Source location unavailable",
                f"The recorded source location no longer exists:\n{location}",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(location)))

    def _remove_selected_documents(self) -> None:
        self._project_document_operations.remove_selected()

    def _confirm_remove_documents(self, document_count: int, entry_count: int) -> bool:
        return QMessageBox.question(
            self,
            "Remove files from project?",
            f"Remove {document_count} file(s) and {entry_count} translation entries "
            "from this project?\n\nOriginal source files on disk will not be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes

    def _refresh_selected_documents(self) -> None:
        self._project_document_operations.refresh_selected()

    def _confirm_document_refresh(self, preview: DocumentRefreshPreview) -> bool:
        return QMessageBox.question(
            self,
            "Refresh files from source?",
            f"Files: {preview.document_count}\n"
            f"New entries: {preview.new_entries}\n"
            f"Changed source: {preview.changed_entries}\n"
            f"Removed entries: {preview.removed_entries}\n"
            f"Unchanged entries: {preview.unchanged_entries}\n\n"
            "Existing translations are preserved. Translations whose source changed "
            "will be marked Needs review.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes

    def _show_document_refresh_error(self, message: str) -> None:
        QMessageBox.critical(self, "Cannot refresh source files", message)

    def _choose_export_file(self, title: str, file_filter: str) -> Path | None:
        path_name, _ = QFileDialog.getSaveFileName(self, title, "", file_filter)
        return Path(path_name) if path_name else None

    def _choose_export_directory(self, title: str) -> Path | None:
        directory_name = QFileDialog.getExistingDirectory(self, title)
        return Path(directory_name) if directory_name else None

    def _show_no_export_selection(self) -> None:
        QMessageBox.information(
            self, "Export files", "Select one or more files in Project Explorer."
        )

    def _confirm_export_warnings(
        self, preflight: ExportPreflight, untranslated_effect: str
    ) -> bool:
        warning_parts: list[str] = []
        if preflight.untranslated_entries:
            warning_parts.append(
                f"{preflight.untranslated_entries} untranslated entries {untranslated_effect}"
            )
        if preflight.entries_with_issues:
            warning_parts.append(f"{preflight.entries_with_issues} entries have validation issues")
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
        translation = self._translation_ui.translation_editor.toPlainText()
        return self._run_entry_action(
            lambda: self._workspace.edit_translation(self._current_entry_id or "", translation),
            "Translation updated",
        )

    def _select_translation_candidate(self, candidate: str) -> None:
        self._entry_operations.select_translation_candidate(candidate)

    def _undo_last_translation(self) -> None:
        self._entry_operations.undo_last_translation()

    def _redo_last_translation(self) -> None:
        self._entry_operations.redo_last_translation()

    def _copy_diagnostics(self) -> None:
        self._project_information.copy_diagnostics()

    def _copy_to_clipboard(self, text: str) -> bool:
        application = cast(QApplication | None, QApplication.instance())
        if application is None:
            return False
        application.clipboard().setText(text)
        return True

    def _show_diagnostics_copied(self) -> None:
        self.statusBar().showMessage(
            self._tr("status.diagnostics_copied", "Diagnostic report copied"), 3000
        )

    def _copy_source_to_translation(self) -> None:
        self._entry_operations.copy_source_to_translation()

    def _apply_and_select_next(self) -> None:
        self._navigation.apply_and_select_next()

    def _select_relative_entry(self, offset: int) -> None:
        self._navigation.select_relative_entry(offset)

    def _current_translation_row(self) -> int:
        current_index = self._translation_ui.table.currentIndex()
        return current_index.row() if current_index.isValid() else 0

    def _select_translation_row(self, row: int) -> None:
        self._translation_ui.table.selectRow(row)
        self._translation_ui.table.scrollTo(self._proxy_model.index(row, 0))

    def _select_relative_issue(self, offset: int) -> None:
        self._navigation.select_relative_issue(offset)

    def _select_next_actionable_entry(self) -> None:
        self._navigation.select_next_actionable_entry()

    def _apply_translation_to_matches(self) -> None:
        self._entry_operations.apply_translation_to_matches()

    def _show_entry_operation_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def _confirm_matching_translation_apply(self, matching_count: int) -> bool:
        return QMessageBox.question(
            self,
            "Apply to matching source",
            f"Apply this translation to {matching_count} matching unlocked entries?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) == QMessageBox.StandardButton.Yes

    def _apply_memory_suggestion(self) -> None:
        if self._memory.suggestion is None:
            return
        self._translation_ui.translation_editor.setPlainText(self._memory.suggestion)
        self._apply_translation()

    def _toggle_entry_approval(self) -> None:
        self._entry_operations.toggle_entry_approval()

    def _set_entry_locked(self, locked: bool) -> None:
        self._entry_operations.set_entry_locked(locked)

    def _translate_selected(self) -> None:
        self._bulk_entries.translate_selected()

    def _translate_all_untranslated(self) -> None:
        self._bulk_entries.translate_all_untranslated()

    def _validate_project(self) -> None:
        self._translation_tools.validate_project()

    def _show_validation_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def _replace_translations(self) -> None:
        self._translation_tools.replace_translations()

    def _ask_translation_replacement(self) -> tuple[str, str] | None:
        search_text, accepted = QInputDialog.getText(
            self, "Replace translations", "Find in translations:"
        )
        if not accepted or not search_text:
            return None
        replacement_text, accepted = QInputDialog.getText(
            self, "Replace translations", "Replace with:"
        )
        if not accepted:
            return None
        return search_text, replacement_text

    def _confirm_translation_replacement(self) -> bool:
        return QMessageBox.question(
            self,
            "Replace translations",
            "Replace all matching text in unlocked translations?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes

    def _approve_selected(self) -> None:
        self._bulk_entries.approve_selected()

    def _select_all_qa_entries(self) -> None:
        self._qa_entries.select_all_qa_entries()

    def _retranslate_all_qa_entries(self) -> None:
        self._qa_entries.retranslate_all_qa_entries()

    def _confirm_qa_retranslation(self, entry_count: int) -> bool:
        return QMessageBox.question(
            self,
            "Re-translate QA entries",
            f"Re-translate {entry_count} QA entries? "
            "Their current translations will be replaced.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) == QMessageBox.StandardButton.Yes

    def _dismiss_selected_ai_issues(self) -> None:
        self._qa_entries.dismiss_selected_ai_issues()

    def _confirm_ai_issue_dismissal(self, entry_count: int) -> bool:
        return QMessageBox.question(
            self,
            "Dismiss AI review issues",
            f"Dismiss AI review issues for {entry_count} selected entries?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) == QMessageBox.StandardButton.Yes

    def _review_selected(self) -> None:
        self._bulk_entries.review_selected()

    def _review_all(self) -> None:
        self._bulk_entries.review_all()

    def _review_progress(self, completed: int, total: int) -> None:
        self._operation_progress.review_progress(completed, total)

    def _show_review_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def _dismiss_ai_review_issue(self) -> None:
        self._translation_tools.dismiss_current_ai_review_issue()

    def _retranslate_current_entry(self) -> None:
        self._bulk_entries.retranslate_current_entry()

    def _reopen_selected(self) -> None:
        self._bulk_entries.reopen_selected()

    def _lock_selected(self) -> None:
        self._bulk_entries.lock_selected()

    def _unlock_selected(self) -> None:
        self._bulk_entries.unlock_selected()

    def _selected_entry_ids(self) -> tuple[str, ...]:
        selected_rows = sorted(
            {index.row() for index in self._translation_ui.table.selectionModel().selectedRows()}
        )
        return tuple(
            self._model.entry_at(
                self._proxy_model.mapToSource(self._proxy_model.index(row, 0)).row()
            ).id
            for row in selected_rows
        )

    def _cancel_translation(self) -> None:
        self._translation_tools.cancel_operation()

    def _translation_progress(self, completed: int, total: int) -> None:
        self._operation_progress.translation_progress(completed, total)

    def _ensure_model_available(self, model: str, reviewer: bool = False) -> bool:
        return self._model_availability.ensure_available(model, reviewer)

    def _choose_available_model(
        self, configured_model: str, installed_models: Sequence[str]
    ) -> str | None:
        download_choice = f"Download configured model: {configured_model}"
        selected, accepted = QInputDialog.getItem(
            self,
            "Choose Ollama model",
            f"Configured model {configured_model} is not installed.",
            (*installed_models, download_choice),
            0,
            False,
        )
        if not accepted:
            return None
        return configured_model if selected == download_choice else selected

    def _confirm_model_download(self, model: str) -> bool:
        return QMessageBox.question(
            self,
            "Ollama model is not installed",
            f"Model {model} is not installed. Download it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        ) == QMessageBox.StandardButton.Yes

    def _offer_ollama_installation(self) -> None:
        if (
            QMessageBox.question(
                self,
                "Ollama is unavailable",
                "LocaForge cannot connect to Ollama. Open the official Windows installer page?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            == QMessageBox.StandardButton.Yes
        ):
            QDesktopServices.openUrl(QUrl("https://ollama.com/download/windows"))

    def _prepare_model_pull_progress(self) -> None:
        self._operation_progress.prepare_model_pull()

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
        self._render_translation_editor(TranslationEditorState.from_entry(entry, busy=self._busy))
        self._quality.refresh_current()
        self._memory.refresh(entry.id)
        self._history.refresh(entry.id)

    def _render_translation_editor(self, state: TranslationEditorState) -> None:
        self._current_entry_id = state.entry_id
        self._current_entry_locked = state.locked
        self._current_entry_max_length = state.max_length
        self._translation_ui.source_editor.setPlainText(state.source_text)
        self._translation_ui.translation_editor.setPlainText(state.translation_text)
        self._translation_ui.model_candidate.setPlainText(state.model_candidate_text)
        self._translation_ui.reviewer_candidate.setPlainText(state.reviewer_candidate_text)
        self._translation_ui.use_model_candidate_button.setEnabled(
            state.model_candidate_enabled
        )
        self._translation_ui.use_reviewer_candidate_button.setEnabled(
            state.reviewer_candidate_enabled
        )
        self._translation_ui.translation_editor.setReadOnly(state.editor_read_only)
        self._translation_ui.copy_source_button.setEnabled(state.copy_source_enabled)
        self._translation_ui.apply_button.setEnabled(state.apply_enabled)
        self._translation_ui.approve_button.setText(state.approval_text)
        self._translation_ui.approve_button.setEnabled(state.approval_enabled)
        self._translation_ui.lock_button.setChecked(state.lock_checked)
        self._translation_ui.lock_button.setEnabled(state.lock_enabled)

    def _refresh_project(self, select_first: bool = True) -> None:
        selected_entry_id = self._current_entry_id
        self._memory.invalidate()
        self._project_overview.refresh()
        snapshot = self._project_refresh.snapshot(
            busy=self._busy,
            has_selected_documents=bool(self._project_overview.selected_document_ids()),
        )
        self._model.set_entries(snapshot.entries)
        self._filters.update_documents(snapshot.documents)
        self._filters.update_entries(snapshot.entries)
        self._update_project_file_count()
        self._refresh_project_file_details(self._project_overview.selected_document_ids())
        self._quality.refresh()
        self._glossary.refresh()
        self._project_action_state.render(snapshot.action_state)
        self._clear_editor()
        self._translation_ui.model_name.setText(snapshot.model_name)
        if snapshot.has_project:
            dirty_mark = " *" if snapshot.project_dirty else ""
            self.setWindowTitle(f"LocaForge — {self._workspace.project.name}{dirty_mark}")
            if selected_entry_id is not None and self._select_visible_entry_by_id(
                selected_entry_id
            ):
                return
            if select_first and self._proxy_model.rowCount():
                self._translation_ui.table.selectRow(0)
            elif not select_first:
                self._translation_ui.table.clearSelection()
                self._translation_ui.table.setCurrentIndex(QModelIndex())
        else:
            self.setWindowTitle("LocaForge")

    def _refresh_project_sidebars(self) -> None:
        if not self._workspace.has_project:
            return
        self._project_overview.refresh()
        self._quality.refresh()

    def _clear_editor(self) -> None:
        self._render_translation_editor(TranslationEditorState.empty())
        self._translation_ui.current_issues.setText("No validation issues")
        self._translation_ui.dismiss_ai_issue_button.setEnabled(False)
        self._translation_ui.retranslate_button.setEnabled(False)
        self._translation_ui.apply_matching_button.setEnabled(False)
        self._history.clear()
        self._memory.clear()

    def _refresh_translation_length(self) -> None:
        self._translation_ui.translation_length.setText(
            format_translation_length(
                len(self._translation_ui.translation_editor.toPlainText()),
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
                self._translation_ui.table.selectRow(proxy_index.row())
                self._translation_ui.table.scrollTo(proxy_index)
                return True
            return False
        return False

    def _run_project_action(self, action: Callable[[], object], success_message: str) -> bool:
        return self._project_actions.run(action, success_message)

    def _show_project_action_error(self, message: str) -> None:
        QMessageBox.critical(self, "LocaForge error", message)

    def _run_entry_action(
        self, action: Callable[[], TranslationEntry], success_message: str
    ) -> bool:
        return self._entry_actions.run(action, success_message)

    def _update_project_window_title(self) -> None:
        dirty_mark = " *" if self._workspace.project.dirty else ""
        self.setWindowTitle(f"LocaForge — {self._workspace.project.name}{dirty_mark}")

    def _show_recent_project_info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def _set_busy(self, busy: bool, refresh: bool = True) -> None:
        self._operation_progress.set_busy(busy, refresh=refresh)

    def _set_busy_state(self, busy: bool) -> None:
        self._busy = busy

    def _sync_autosave(self) -> None:
        self._autosave_policy.sync()

    def _open_application_settings(self) -> None:
        if self._busy:
            return
        original_server_url = self._application_settings.ollama_server_url
        dialog = ApplicationSettingsDialog(
            self._application_settings,
            self,
            test_ollama=self._ollama_connection_test,
            list_models=self._ollama_models,
            pull_model=self._pull_model_from_settings,
            open_installer=self._open_ollama_installer,
            localization=self._localization,
            open_localization_folder=self._open_localization_folder,
        )
        def model_pull_started(model: str) -> None:
            dialog.set_model_pull_running(True, f"Downloading {model}…")

        def model_pull_completed(model: str, success: bool, message: str) -> None:
            dialog.set_model_pull_running(
                False,
                f"Installed {model}" if success else f"Download failed — {message}",
            )

        self._model_pull.started.connect(model_pull_started)
        self._model_pull.completed.connect(model_pull_completed)
        result = dialog.exec()
        self._model_pull.started.disconnect(model_pull_started)
        self._model_pull.completed.disconnect(model_pull_completed)
        if result != QDialog.DialogCode.Accepted:
            self._application_settings_controller.restore_ollama_server(original_server_url)
            return
        self._application_settings_controller.apply(dialog.settings())

    def _set_current_application_settings(self, settings: ApplicationSettings) -> None:
        self._application_settings = settings

    def _show_application_settings_saved(self) -> None:
        status = self._tr("main.settings_saved", "Application settings saved")
        self.statusBar().showMessage(status, 3000)

    def _ollama_connection_test(self, server_url: str) -> tuple[bool, str]:
        client = OllamaClient(server_url or "http://127.0.0.1:11434")
        if client.health_check():
            return True, "Connected"
        return False, "Unavailable — cannot connect to Ollama"

    def _ollama_models(self, server_url: str) -> tuple[str, ...]:
        return OllamaClient(server_url or "http://127.0.0.1:11434").list_models()

    def _pull_model_from_settings(self, server_url: str, model: str) -> bool:
        client = OllamaClient(server_url or "http://127.0.0.1:11434")
        return self._model_pull.start(model, lambda: client.pull_model(model))

    def _configure_ollama_server(self, server_url: str) -> None:
        self._workspace.set_llm_client(OllamaClient(server_url or "http://127.0.0.1:11434"))

    def _open_ollama_installer(self) -> None:
        QDesktopServices.openUrl(QUrl("https://ollama.com/download/windows"))

    def _open_localization_folder(self) -> None:
        if self._localization is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._localization.user_directory)))

    def _apply_application_settings(self) -> None:
        self._appearance.render(self._application_settings)

    def _autosave_succeeded(self) -> None:
        self._autosave_policy.succeeded()

    def _autosave_failed(self, message: str) -> None:
        self._autosave_policy.failed(message)

    def _show_autosave_failure(self, message: str) -> None:
        QMessageBox.warning(self, "Autosave failed", message)

    def _restore_window_layout(self) -> None:
        self._window_layout.restore()

    def _persist_window_layout(self) -> None:
        self._window_layout.persist()

    def _reset_window_layout(self) -> None:
        self._window_layout.reset()

    def _confirm_unsaved_changes(self) -> bool:
        return self._window_close.confirm_unsaved_changes()

    def _ask_unsaved_changes(self) -> UnsavedChangesDecision:
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
            return UnsavedChangesDecision.CANCEL
        if response == QMessageBox.StandardButton.Discard:
            return UnsavedChangesDecision.DISCARD
        return UnsavedChangesDecision.SAVE

    def _show_unsaved_save_error(self, message: str) -> None:
        QMessageBox.critical(self, "Cannot save project", message)

    def _show_close_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._window_close.request_close():
            event.ignore()
            return
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
            (
                self._application_settings.default_source_language,
                self._application_settings.default_target_language,
            ),
        )
        if dialog.exec() != ProjectSetupDialog.DialogCode.Accepted:
            return None
        return dialog.language_pair()
