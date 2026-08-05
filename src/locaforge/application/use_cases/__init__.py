"""Application workflows for projects and translations."""

from locaforge.application.use_cases.apply_translation_to_matches import (
    ApplyTranslationToMatches,
)
from locaforge.application.use_cases.create_project_from_csv import CreateProjectFromCsv
from locaforge.application.use_cases.create_project_from_json import CreateProjectFromJson
from locaforge.application.use_cases.create_project_from_po import CreateProjectFromPo
from locaforge.application.use_cases.create_project_from_xml import CreateProjectFromXml
from locaforge.application.use_cases.edit_translation import EditTranslation
from locaforge.application.use_cases.export_project_csv import ExportProjectCsv
from locaforge.application.use_cases.export_project_json import ExportProjectJson
from locaforge.application.use_cases.export_project_po import ExportProjectPo
from locaforge.application.use_cases.export_project_xml import ExportProjectXml
from locaforge.application.use_cases.find_translation_memory_match import (
    FindTranslationMemoryMatch,
)
from locaforge.application.use_cases.find_translation_memory_matches import (
    FindTranslationMemoryMatches,
)
from locaforge.application.use_cases.open_project_file import OpenProjectFile
from locaforge.application.use_cases.restore_entry_revision import RestoreEntryRevision
from locaforge.application.use_cases.save_project import SaveProject
from locaforge.application.use_cases.save_project_file import SaveProjectFile
from locaforge.application.use_cases.set_entries_approval import SetEntriesApproval
from locaforge.application.use_cases.set_entries_locked import SetEntriesLocked
from locaforge.application.use_cases.set_entry_approval import SetEntryApproval
from locaforge.application.use_cases.set_entry_locked import SetEntryLocked
from locaforge.application.use_cases.translate_batch import TranslateBatch
from locaforge.application.use_cases.update_model_settings import UpdateModelSettings
from locaforge.application.use_cases.validate_project import ValidateProject

__all__ = [
    "ApplyTranslationToMatches",
    "CreateProjectFromCsv",
    "CreateProjectFromJson",
    "CreateProjectFromPo",
    "CreateProjectFromXml",
    "EditTranslation",
    "ExportProjectCsv",
    "ExportProjectJson",
    "ExportProjectPo",
    "ExportProjectXml",
    "FindTranslationMemoryMatch",
    "FindTranslationMemoryMatches",
    "OpenProjectFile",
    "RestoreEntryRevision",
    "SaveProject",
    "SaveProjectFile",
    "SetEntryApproval",
    "SetEntryLocked",
    "SetEntriesApproval",
    "SetEntriesLocked",
    "TranslateBatch",
    "UpdateModelSettings",
    "ValidateProject",
]
