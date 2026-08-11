"""Construction of the project-file workspace."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class ProjectWorkspaceWidgets:
    content: QSplitter
    explorer: QListWidget
    file_tree: QTreeWidget
    file_search: QLineEdit
    file_count: QLabel
    add_files_button: QPushButton
    add_folder_button: QPushButton
    export_selected_button: QPushButton
    remove_selected_button: QPushButton
    refresh_selected_button: QPushButton
    settings_button: QPushButton
    context_button: QPushButton
    file_details: QLabel


def build_project_workspace_widgets(
    parent: QWidget,
    *,
    add_files: Callable[[], None],
    add_folder: Callable[[], None],
    export_selected: Callable[[], None],
    remove_selected: Callable[[], None],
    refresh_selected: Callable[[], None],
    edit_settings: Callable[[], None],
    preview_context: Callable[[], None],
    show_context_menu: Callable[[QPoint], None],
    open_document: Callable[[object], None],
) -> ProjectWorkspaceWidgets:
    """Create the Project tab and connect its local interaction callbacks."""
    explorer = QListWidget(parent)
    file_tree = QTreeWidget(parent)
    file_tree.setColumnCount(3)
    file_tree.setHeaderLabels(("Name", "Format", "Progress"))
    file_tree.setAlternatingRowColors(True)
    file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    file_tree.customContextMenuRequested.connect(show_context_menu)
    file_tree.itemDoubleClicked.connect(
        lambda item, _column: open_document(
            item.data(0, Qt.ItemDataRole.UserRole)
        )
    )

    file_search = QLineEdit(parent)
    file_search.setPlaceholderText("Search project files...")
    file_search.setClearButtonEnabled(True)
    file_search.setToolTip("Filter project files by name or relative path")
    file_count = QLabel("0 / 0 files", parent)

    add_files_button = QPushButton("Add files...", parent)
    add_files_button.clicked.connect(add_files)
    add_folder_button = QPushButton("Add folder...", parent)
    add_folder_button.clicked.connect(add_folder)
    export_selected_button = QPushButton("Export selected...", parent)
    export_selected_button.clicked.connect(export_selected)
    remove_selected_button = QPushButton("Remove...", parent)
    remove_selected_button.setToolTip(
        "Remove selected files from the project without deleting source files"
    )
    remove_selected_button.clicked.connect(remove_selected)
    refresh_selected_button = QPushButton("Refresh", parent)
    refresh_selected_button.setToolTip(
        "Re-import selected files from their recorded source locations"
    )
    refresh_selected_button.clicked.connect(refresh_selected)
    settings_button = QPushButton("Settings...", parent)
    settings_button.clicked.connect(edit_settings)
    context_button = QPushButton("AI context...", parent)
    context_button.setToolTip(
        "Preview the project information added to translation and review prompts"
    )
    context_button.clicked.connect(preview_context)

    project_buttons = QHBoxLayout()
    for button in (
        add_files_button,
        add_folder_button,
        export_selected_button,
        remove_selected_button,
        refresh_selected_button,
        settings_button,
        context_button,
    ):
        project_buttons.addWidget(button)

    project_widget = QWidget(parent)
    project_layout = QVBoxLayout(project_widget)
    project_layout.addWidget(QLabel("Project summary", parent))
    project_layout.addWidget(explorer)
    project_layout.addWidget(QLabel("Files", parent))
    project_layout.addWidget(file_search)
    project_layout.addWidget(file_count)
    project_layout.addWidget(file_tree, 2)
    project_layout.addLayout(project_buttons)

    file_details = QLabel("Select a project file to see its details", parent)
    file_details.setAlignment(
        Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
    )
    file_details.setTextFormat(Qt.TextFormat.PlainText)
    file_details.setWordWrap(True)
    file_details.setMinimumWidth(280)
    content = QSplitter(Qt.Orientation.Horizontal, parent)
    content.addWidget(project_widget)
    content.addWidget(file_details)
    content.setStretchFactor(0, 3)
    content.setStretchFactor(1, 2)
    return ProjectWorkspaceWidgets(
        content,
        explorer,
        file_tree,
        file_search,
        file_count,
        add_files_button,
        add_folder_button,
        export_selected_button,
        remove_selected_button,
        refresh_selected_button,
        settings_button,
        context_button,
        file_details,
    )
