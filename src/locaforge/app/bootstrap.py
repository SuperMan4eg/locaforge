"""Desktop application composition root."""

from __future__ import annotations

import json
import logging
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths
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
from locaforge.infrastructure.metadata.wikipedia_lookup import (
    WikipediaProjectMetadataLookup,
)
from locaforge.infrastructure.persistence.lfproj_container import LfprojContainer
from locaforge.infrastructure.persistence.sqlite_glossary import SQLiteGlossary
from locaforge.infrastructure.persistence.sqlite_project_repository_factory import (
    SQLiteProjectRepositoryFactory,
)
from locaforge.infrastructure.persistence.sqlite_translation_memory import (
    SQLiteTranslationMemory,
)
from locaforge.presentation.application_settings import ApplicationSettingsStore
from locaforge.presentation.localization import LocalizationManager
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
        WikipediaProjectMetadataLookup(),
    )


def run_self_test() -> None:
    """Exercise a packaged build's persistent project lifecycle without user data."""
    with tempfile.TemporaryDirectory(prefix="locaforge-self-test-") as temporary_directory:
        root = Path(temporary_directory)
        source_path = root / "source.json"
        project_path = root / "self-test.lfproj"
        export_path = root / "exported.json"
        source_path.write_text('{"greeting": "Hello"}', encoding="utf-8")
        workspace = build_workspace(root / "data")
        project = workspace.create_from_json(source_path, project_path, "en", "ru")
        workspace.edit_translation(project.entries[0].id, "Привет")
        workspace.save()
        reopened = build_workspace(root / "reopened-data")
        reopened.open(project_path)
        reopened.export_json(export_path)
        exported = json.loads(export_path.read_text(encoding="utf-8"))
        if exported != {"greeting": "Привет"}:
            raise RuntimeError("Packaged project lifecycle self-test produced invalid output")


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("LocaForge")
    application.setOrganizationName("LocaForge")
    data_root = Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    )
    log_path = configure_logging(data_root)
    install_exception_handler(log_path, show_dialog="--self-test" not in sys.argv)
    logging.getLogger(LOGGER_NAME).info("Starting LocaForge")
    if "--self-test" in sys.argv:
        run_self_test()
        return 0
    settings_store = QSettings()
    settings = ApplicationSettingsStore(settings_store).load()
    localization = LocalizationManager(data_root / "localizations", settings.ui_locale)
    localization.install(application)
    window = MainWindow(
        build_workspace(data_root),
        application_settings=ApplicationSettingsStore(settings_store),
        localization=localization,
    )
    window.show()
    if "--smoke-test" in sys.argv:
        application.processEvents()
        window.close()
        application.processEvents()
        return 0
    return application.exec()
