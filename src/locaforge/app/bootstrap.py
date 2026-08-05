"""Desktop application composition root."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QTimer
from PySide6.QtWidgets import QApplication

from locaforge.app.exception_handler import install_exception_handler
from locaforge.app.logging_config import LOGGER_NAME, configure_logging
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.infrastructure.formats.csv_format import CsvFileFormat
from locaforge.infrastructure.formats.glossary_csv import CsvGlossaryFormat
from locaforge.infrastructure.formats.json_format import JsonFileExporter, JsonFileImporter
from locaforge.infrastructure.formats.po_format import PoFileFormat
from locaforge.infrastructure.formats.xml_format import XmlFileFormat
from locaforge.infrastructure.llm.ollama_client import OllamaClient
from locaforge.infrastructure.persistence.lfproj_container import LfprojContainer
from locaforge.infrastructure.persistence.sqlite_glossary import SQLiteGlossary
from locaforge.infrastructure.persistence.sqlite_project_repository_factory import (
    SQLiteProjectRepositoryFactory,
)
from locaforge.infrastructure.persistence.sqlite_translation_memory import (
    SQLiteTranslationMemory,
)
from locaforge.presentation.main_window import MainWindow


def build_workspace(data_root: Path) -> ProjectWorkspace:
    po_format = PoFileFormat()
    csv_format = CsvFileFormat()
    xml_format = XmlFileFormat()
    return ProjectWorkspace(
        JsonFileImporter(),
        JsonFileExporter(),
        LfprojContainer(data_root / "workspaces"),
        SQLiteProjectRepositoryFactory(),
        OllamaClient(),
        SQLiteTranslationMemory(data_root / "tm.db"),
        SQLiteGlossary(data_root / "glossary.db"),
        CsvGlossaryFormat(),
        po_format,
        po_format,
        csv_format,
        csv_format,
        xml_format,
        xml_format,
    )


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("LocaForge")
    application.setOrganizationName("LocaForge")
    data_root = Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    )
    log_path = configure_logging(data_root)
    install_exception_handler(log_path)
    logging.getLogger(LOGGER_NAME).info("Starting LocaForge")
    window = MainWindow(build_workspace(data_root))
    window.show()
    if "--smoke-test" in sys.argv:
        QTimer.singleShot(1000, application.quit)
    return application.exec()
