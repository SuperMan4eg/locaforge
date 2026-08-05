"""Localization CSV adapter with dialect and column preservation."""

from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from locaforge.application.ports.csv_format import CsvFieldMapping
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project

type CsvRow = dict[str, str]
type CsvDialectData = dict[str, str | int | bool | None]


class InvalidCsvError(ValueError):
    pass


class CsvFileFormat:
    def inspect_fields(self, path: Path) -> tuple[str, ...]:
        _, fieldnames, _, _ = self._read(path)
        return tuple(fieldnames)

    def import_file(
        self,
        path: Path,
        source_language: str,
        target_language: str,
        field_mapping: CsvFieldMapping,
    ) -> Project:
        rows, fieldnames, dialect, line_terminator = self._read(path)
        self._validate_mapping(fieldnames, field_mapping)
        entries: list[TranslationEntry] = []
        for row_index, row in enumerate(rows):
            source = row[field_mapping.source_field]
            if not source:
                continue
            existing = row[field_mapping.target_field]
            translation = (
                existing
                if field_mapping.import_existing_translations and existing
                else None
            )
            key = row.get(field_mapping.key_field) if field_mapping.key_field else None
            entries.append(
                TranslationEntry(
                    id=str(uuid4()),
                    key_path=("rows", row_index, field_mapping.target_field),
                    source=source,
                    translation=translation,
                    status=(
                        EntryStatus.NEEDS_REVIEW
                        if translation is not None
                        else EntryStatus.UNTRANSLATED
                    ),
                    key=key or None,
                )
            )
        return Project(
            id=str(uuid4()),
            name=path.stem,
            source_language=source_language,
            target_language=target_language,
            entries=entries,
            source_document={
                "format": "csv",
                "fieldnames": fieldnames,
                "rows": rows,
                "dialect": dialect,
                "line_terminator": line_terminator,
            },
        )

    def export_file(self, project: Project, destination: Path) -> None:
        document = project.source_document
        if not isinstance(document, dict) or document.get("format") != "csv":
            raise InvalidCsvError("Project has no CSV source document")
        fieldnames = document.get("fieldnames")
        raw_rows = document.get("rows")
        raw_dialect = document.get("dialect")
        if (
            not isinstance(fieldnames, list)
            or not all(isinstance(field, str) for field in fieldnames)
            or not isinstance(raw_rows, list)
            or not isinstance(raw_dialect, dict)
        ):
            raise InvalidCsvError("CSV source document is invalid")
        rows = cast(list[CsvRow], deepcopy(raw_rows))
        for entry in project.entries:
            if len(entry.key_path) != 3:
                continue
            _, row_index, target_field = entry.key_path
            rows[int(row_index)][str(target_field)] = entry.translation or ""
        dialect = cast(CsvDialectData, raw_dialect)
        line_terminator = document.get("line_terminator", "\n")
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=cast(list[str], fieldnames),
                    delimiter=str(dialect["delimiter"]),
                    quotechar=cast(str | None, dialect["quotechar"]),
                    doublequote=bool(dialect["doublequote"]),
                    escapechar=cast(str | None, dialect["escapechar"]),
                    lineterminator=str(line_terminator),
                    quoting=cast(Any, dialect["quoting"]),
                    skipinitialspace=bool(dialect["skipinitialspace"]),
                )
                writer.writeheader()
                writer.writerows(rows)
        except (OSError, csv.Error) as error:
            raise InvalidCsvError(f"Cannot export CSV file to {destination}") from error

    def _read(
        self, path: Path
    ) -> tuple[list[CsvRow], list[str], CsvDialectData, str]:
        try:
            text = path.read_text(encoding="utf-8-sig")
            dialect_object = self._detect_dialect(text)
            reader = csv.DictReader(text.splitlines(), dialect=dialect_object)
            raw_fieldnames = reader.fieldnames
            if not raw_fieldnames or any(not field for field in raw_fieldnames):
                raise InvalidCsvError("CSV file must have a header row")
            fieldnames = list(raw_fieldnames)
            if len(set(fieldnames)) != len(fieldnames):
                raise InvalidCsvError("CSV header contains duplicate fields")
            rows: list[CsvRow] = []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise InvalidCsvError("CSV row does not match its header")
                rows.append(cast(CsvRow, row))
        except (OSError, UnicodeDecodeError, csv.Error) as error:
            raise InvalidCsvError(f"Cannot import CSV file {path.name!r}") from error
        dialect: CsvDialectData = {
            "delimiter": dialect_object.delimiter,
            "quotechar": dialect_object.quotechar,
            "doublequote": dialect_object.doublequote,
            "escapechar": dialect_object.escapechar,
            "quoting": dialect_object.quoting,
            "skipinitialspace": dialect_object.skipinitialspace,
        }
        line_terminator = "\r\n" if "\r\n" in text else "\n"
        return rows, fieldnames, dialect, line_terminator

    @staticmethod
    def _detect_dialect(text: str) -> type[csv.Dialect] | csv.Dialect:
        try:
            return csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
        except csv.Error:
            return csv.excel

    @staticmethod
    def _validate_mapping(
        fieldnames: list[str], mapping: CsvFieldMapping
    ) -> None:
        selected = (mapping.source_field, mapping.target_field)
        if any(field not in fieldnames for field in selected):
            raise InvalidCsvError("Selected CSV fields do not exist")
        if mapping.source_field == mapping.target_field:
            raise InvalidCsvError("Source and target CSV fields must differ")
        if mapping.key_field is not None and mapping.key_field not in fieldnames:
            raise InvalidCsvError("Selected CSV key field does not exist")
