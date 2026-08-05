"""Glossary dock interaction orchestration."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QWidget,
)

from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.glossary import GlossaryTerm

type ProjectAction = Callable[[], object]
type ActionRunner = Callable[[ProjectAction, str], bool]


class GlossaryController(QObject):
    """Owns glossary dock state and user actions."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        terms: QListWidget,
        add_button: QPushButton,
        remove_button: QPushButton,
        import_button: QPushButton,
        export_button: QPushButton,
        run_action: ActionRunner,
        source_text: Callable[[], str],
        translation_text: Callable[[], str],
        is_busy: Callable[[], bool],
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._terms = terms
        self._add_button = add_button
        self._remove_button = remove_button
        self._import_button = import_button
        self._export_button = export_button
        self._run_action = run_action
        self._source_text = source_text
        self._translation_text = translation_text
        self._is_busy = is_busy
        self._parent = parent
        terms.currentItemChanged.connect(self._selection_changed)
        add_button.clicked.connect(self.add_term)
        remove_button.clicked.connect(self.remove_term)
        import_button.clicked.connect(self.import_csv)
        export_button.clicked.connect(self.export_csv)

    def refresh(self) -> None:
        self._terms.clear()
        if not self._workspace.has_project:
            return
        for term in self._workspace.glossary_terms():
            sensitivity = " [case-sensitive]" if term.case_sensitive else ""
            item = QListWidgetItem(f"{term.source} -> {term.target}{sensitivity}")
            item.setData(Qt.ItemDataRole.UserRole, term)
            self._terms.addItem(item)

    def set_enabled(self, enabled: bool) -> None:
        self._add_button.setEnabled(enabled)
        self._import_button.setEnabled(enabled)
        self._export_button.setEnabled(enabled)
        self._remove_button.setEnabled(enabled and self._terms.currentItem() is not None)

    def add_term(self) -> None:
        if not self._is_available():
            return
        source, accepted = QInputDialog.getText(
            self._parent,
            "Add glossary term",
            "Source term:",
            text=self._source_text(),
        )
        if not accepted or not source.strip():
            return
        target, accepted = QInputDialog.getText(
            self._parent,
            "Add glossary term",
            "Required translation:",
            text=self._translation_text(),
        )
        if not accepted or not target.strip():
            return
        case_sensitive = QMessageBox.question(
            self._parent,
            "Glossary term",
            "Match the source term case-sensitively?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes
        self._run_action(
            lambda: self._workspace.store_glossary_term(
                source.strip(), target.strip(), case_sensitive
            ),
            "Glossary term saved",
        )

    def remove_term(self) -> None:
        item = self._terms.currentItem()
        term = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(term, GlossaryTerm) or not self._is_available():
            return
        if QMessageBox.question(
            self._parent,
            "Remove glossary term",
            f"Remove {term.source!r} -> {term.target!r}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._run_action(
            lambda: self._workspace.remove_glossary_term(term),
            "Glossary term removed",
        )

    def import_csv(self) -> None:
        if not self._is_available():
            return
        path_name, _ = QFileDialog.getOpenFileName(
            self._parent, "Import glossary CSV", "", "CSV files (*.csv)"
        )
        if path_name:
            self._run_action(
                lambda: self._workspace.import_glossary_csv(Path(path_name)),
                "Glossary CSV imported",
            )

    def export_csv(self) -> None:
        if not self._is_available():
            return
        path_name, _ = QFileDialog.getSaveFileName(
            self._parent, "Export glossary CSV", "", "CSV files (*.csv)"
        )
        if not path_name:
            return
        destination = Path(path_name)
        if destination.suffix.lower() != ".csv":
            destination = destination.with_suffix(".csv")
        self._run_action(
            lambda: self._workspace.export_glossary_csv(destination),
            "Glossary CSV exported",
        )

    def _selection_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        del previous
        self._remove_button.setEnabled(current is not None and self._is_available())

    def _is_available(self) -> bool:
        return self._workspace.has_project and not self._is_busy()
