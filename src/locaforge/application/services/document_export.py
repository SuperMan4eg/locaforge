"""Atomic export of selected project documents to their original paths."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from locaforge.application.services.project_path import is_safe_project_path
from locaforge.domain.project import Project

type DocumentExporter = Callable[[Project, str, Path], None]


class DocumentExportService:
    """Stage document exports and publish them only after every export succeeds."""

    def export(
        self,
        project: Project,
        document_ids: Sequence[str] | set[str] | frozenset[str],
        destination_directory: Path,
        export_document: DocumentExporter,
    ) -> tuple[Path, ...]:
        selected_ids = frozenset(document_ids)
        if not selected_ids:
            raise ValueError("Select at least one project file to export")
        known_ids = {document.id for document in project.documents}
        if selected_ids - known_ids:
            raise ValueError("One or more selected project files do not exist")
        destination_directory.parent.mkdir(parents=True, exist_ok=True)
        exported_relative_paths: list[Path] = []
        with tempfile.TemporaryDirectory(
            prefix=".locaforge-export-", dir=destination_directory.parent
        ) as temporary_name:
            temporary_directory = Path(temporary_name)
            for document in project.documents:
                if document.id not in selected_ids:
                    continue
                if not is_safe_project_path(document.source_path):
                    raise ValueError(
                        f"Document {document.name!r} has an unsafe export path"
                    )
                relative_path = Path(document.source_path)
                document_project = Project(
                    id=project.id,
                    name=document.name,
                    source_language=project.source_language,
                    target_language=project.target_language,
                    entries=[
                        entry for entry in project.entries if entry.document_id == document.id
                    ],
                    source_document=document.source_document,
                    model_settings=project.model_settings,
                    documents=[document],
                )
                staged_path = temporary_directory / relative_path
                staged_path.parent.mkdir(parents=True, exist_ok=True)
                export_document(document_project, document.source_format, staged_path)
                exported_relative_paths.append(relative_path)

            destination_directory.mkdir(parents=True, exist_ok=True)
            for relative_path in exported_relative_paths:
                staged_path = temporary_directory / relative_path
                destination_path = destination_directory / relative_path
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged_path, destination_path)
        return tuple(destination_directory / path for path in exported_relative_paths)
