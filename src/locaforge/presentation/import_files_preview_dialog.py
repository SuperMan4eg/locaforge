"""Preview the files discovered by the unified import workflow."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from locaforge.presentation.import_file_selection import duplicate_project_paths
from locaforge.presentation.localization import tr


class ImportFilesPreviewDialog(QDialog):
    def __init__(
        self,
        paths: Sequence[Path],
        project_paths: dict[Path, str] | None = None,
        existing_project_paths: Sequence[str] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add files to project")
        self.resize(760, 440)
        self._paths = tuple(paths)
        displayed_paths = project_paths or {path: path.name for path in self._paths}
        self._existing_project_paths = {
            self._normalize_project_path(path).casefold()
            for path in existing_project_paths
        }
        introduction = QLabel(
            tr(
                "import.introduction",
                "{count} supported localization file(s) will be added to the project. "
                "Edit a Project path to resolve a conflict.",
                count=len(paths),
            ),
            self,
        )
        destination_row = QHBoxLayout()
        destination_row.addWidget(QLabel("Destination folder", self))
        self._destination_folder = QLineEdit(self)
        self._destination_folder.setObjectName("importDestinationFolder")
        self._destination_folder.setPlaceholderText("For example: locale/ui")
        destination_row.addWidget(self._destination_folder, 1)
        self._apply_destination = QPushButton("Apply to all", self)
        self._apply_destination.setObjectName("applyImportDestination")
        self._apply_destination.setEnabled(False)
        self._apply_destination.clicked.connect(self._apply_destination_folder)
        self._destination_folder.textChanged.connect(
            self._update_destination_button
        )
        destination_row.addWidget(self._apply_destination)
        self._table = QTableWidget(len(paths), 3, self)
        self._table.setHorizontalHeaderLabels(
            ("Project path", "Format", "Source location")
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for row, path in enumerate(self._paths):
            self._table.setItem(row, 0, QTableWidgetItem(displayed_paths[path]))
            format_item = QTableWidgetItem(path.suffix.lstrip(".").upper())
            format_item.setFlags(format_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 1, format_item)
            source_item = QTableWidgetItem(str(path.parent))
            source_item.setFlags(source_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 2, source_item)
        self._table.resizeColumnsToContents()
        self.warning = QLabel(self)
        self.warning.setWordWrap(True)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok,
            self,
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Continue")
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        self._table.itemChanged.connect(self._validate_paths)
        layout = QVBoxLayout(self)
        layout.addWidget(introduction)
        layout.addLayout(destination_row)
        layout.addWidget(self._table)
        layout.addWidget(self.warning)
        layout.addWidget(self._buttons)
        self._validate_paths()

    def project_paths(self) -> dict[Path, str]:
        """Return normalized project paths edited in the preview."""
        result: dict[Path, str] = {}
        for row, path in enumerate(self._paths):
            item = self._table.item(row, 0)
            result[path] = self._normalize_project_path(
                item.text() if item is not None else ""
            )
        return result

    @staticmethod
    def _normalize_project_path(value: str) -> str:
        return value.strip().replace("\\", "/")

    def _update_destination_button(self) -> None:
        value = self._normalize_project_path(self._destination_folder.text()).rstrip(
            "/"
        )
        self._apply_destination.setEnabled(
            bool(value) and self._is_safe_project_path(f"{value}/placeholder")
        )

    def _apply_destination_folder(self) -> None:
        destination = self._normalize_project_path(
            self._destination_folder.text()
        ).rstrip("/")
        if not destination:
            return
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is not None:
                current_path = self._normalize_project_path(item.text()).lstrip("/")
                item.setText(f"{destination}/{current_path}")

    @staticmethod
    def _is_safe_project_path(value: str) -> bool:
        if not value or value.endswith("/"):
            return False
        posix_path = PurePosixPath(value)
        windows_path = PureWindowsPath(value)
        return (
            not posix_path.is_absolute()
            and not windows_path.is_absolute()
            and not windows_path.drive
            and ".." not in posix_path.parts
            and posix_path.name not in {"", ".", ".."}
        )

    def _validate_paths(self) -> None:
        paths = tuple(self.project_paths().values())
        unsafe = {path for path in paths if not self._is_safe_project_path(path)}
        duplicates = duplicate_project_paths(paths)
        existing_conflicts = {
            path
            for path in paths
            if path.casefold() in self._existing_project_paths
        }
        problems: list[str] = []
        if unsafe:
            problems.append(
                tr("import.unsafe_paths", "unsafe or empty paths: ")
                + ", ".join(sorted(unsafe, key=str.casefold))
            )
        if duplicates:
            problems.append(
                tr("import.duplicate_paths", "duplicate paths in selection: ")
                + ", ".join(sorted(duplicates, key=str.casefold))
            )
        if existing_conflicts:
            problems.append(
                tr("import.already_in_project", "already in project: ")
                + ", ".join(sorted(existing_conflicts, key=str.casefold))
            )
        self.warning.setText(
            tr(
                "import.path_warning",
                "Files in one project must have unique relative paths and remain safe. ",
            )
            + "; ".join(problems)
            if problems
            else ""
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            not problems
        )
