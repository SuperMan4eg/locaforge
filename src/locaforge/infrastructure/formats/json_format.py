"""JSON file adapters for the LocaForge MVP."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from locaforge.application.ports.json_format import JsonFieldMapping
from locaforge.domain.entry import EntryStatus, JsonPath, TranslationEntry
from locaforge.domain.project import Project

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


class InvalidJsonError(ValueError):
    """Raised when a source file is not valid JSON."""


class UnsupportedJsonShapeError(ValueError):
    """Raised when a source JSON document cannot be handled by the MVP."""


class JsonFileImporter:
    """Imports every JSON string value as a translation entry."""

    def import_file(
        self,
        path: Path,
        source_language: str,
        target_language: str,
        field_mapping: JsonFieldMapping | None = None,
    ) -> Project:
        document = self._read_document(path)
        entries = (
            self._collect_mapped_entries(document, field_mapping)
            if field_mapping is not None
            else list(self._collect_entries(document))
        )
        return Project(
            id=str(uuid4()),
            name=path.stem,
            source_language=source_language,
            target_language=target_language,
            entries=entries,
            source_document=document,
        )

    def inspect_fields(self, path: Path) -> tuple[str, ...]:
        document = self._read_document(path)
        if not isinstance(document, list) or not document:
            return ()
        fields = {
            key
            for item in document
            if isinstance(item, dict)
            for key, value in item.items()
            if isinstance(value, str)
        }
        return tuple(sorted(fields))

    @staticmethod
    def _collect_mapped_entries(
        document: JsonValue, mapping: JsonFieldMapping
    ) -> list[TranslationEntry]:
        if not isinstance(document, list):
            raise UnsupportedJsonShapeError("Field mapping requires a JSON array")
        entries: list[TranslationEntry] = []
        for index, item in enumerate(document):
            if not isinstance(item, dict):
                continue
            source = item.get(mapping.source_field)
            if not isinstance(source, str):
                continue
            existing_translation = item.get(mapping.target_field)
            translation = (
                existing_translation
                if mapping.import_existing_translations
                and isinstance(existing_translation, str)
                and existing_translation
                else None
            )
            key = item.get(mapping.key_field) if mapping.key_field else None
            entries.append(
                TranslationEntry(
                    id=str(uuid4()),
                    key_path=(index, mapping.target_field),
                    source=source,
                    key=key if isinstance(key, str) else None,
                    translation=translation,
                    status=(
                        EntryStatus.NEEDS_REVIEW
                        if translation is not None
                        else EntryStatus.UNTRANSLATED
                    ),
                )
            )
        return entries

    @staticmethod
    def _read_document(path: Path) -> JsonValue:
        try:
            document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise InvalidJsonError(f"Cannot import JSON file {path.name!r}") from error

        if not isinstance(document, (dict, list)):
            raise UnsupportedJsonShapeError("The JSON root must be an object or an array")
        return document

    def _collect_entries(
        self, value: JsonValue, path: JsonPath = ()
    ) -> list[TranslationEntry]:
        if isinstance(value, str):
            return [
                TranslationEntry(
                    id=str(uuid4()),
                    key_path=path,
                    source=value,
                )
            ]
        if isinstance(value, list):
            return [
                entry
                for index, item in enumerate(value)
                for entry in self._collect_entries(item, (*path, index))
            ]
        if isinstance(value, dict):
            return [
                entry
                for key, item in value.items()
                for entry in self._collect_entries(item, (*path, key))
            ]
        return []


class JsonFileExporter:
    """Writes translations into a copy of the imported JSON document."""

    def export_file(self, project: Project, destination: Path) -> None:
        if not isinstance(project.source_document, (dict, list)):
            raise UnsupportedJsonShapeError("Project has no JSON source document")

        document = deepcopy(project.source_document)
        for entry in project.entries:
            if entry.translation:
                self._replace_value(document, entry.key_path, entry.translation)

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as error:
            raise OSError(f"Cannot export JSON file to {destination}") from error

    @staticmethod
    def _replace_value(document: JsonValue, path: JsonPath, translation: str) -> None:
        if not path:
            raise UnsupportedJsonShapeError("A JSON translation entry must have a key path")

        parent: JsonValue = document
        for part in path[:-1]:
            if isinstance(parent, dict) and isinstance(part, str):
                parent = parent[part]
            elif isinstance(parent, list) and isinstance(part, int):
                parent = parent[part]
            else:
                raise UnsupportedJsonShapeError("Entry path does not match its source document")

        last_part = path[-1]
        if isinstance(parent, dict) and isinstance(last_part, str):
            parent[last_part] = translation
        elif isinstance(parent, list) and isinstance(last_part, int):
            parent[last_part] = translation
        else:
            raise UnsupportedJsonShapeError("Entry path does not match its source document")
