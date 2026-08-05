"""CSV glossary import and export."""

from __future__ import annotations

import csv
from pathlib import Path

from locaforge.domain.glossary import GlossaryTerm


class CsvGlossaryFormat:
    """Reads and writes source,target,case_sensitive glossary CSV files."""

    _REQUIRED_COLUMNS = {"source", "target"}

    def import_file(
        self,
        path: Path,
        source_language: str,
        target_language: str,
    ) -> tuple[GlossaryTerm, ...]:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                columns = set(reader.fieldnames or ())
                if not self._REQUIRED_COLUMNS.issubset(columns):
                    raise ValueError("Glossary CSV must have source and target columns")
                return tuple(
                    self._term_from_row(
                        row,
                        source_language,
                        target_language,
                        line_number,
                    )
                    for line_number, row in enumerate(reader, start=2)
                )
        except OSError as error:
            raise OSError(f"Cannot read glossary CSV file {path}") from error

    def export_file(self, terms: tuple[GlossaryTerm, ...], path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=("source", "target", "case_sensitive"),
                )
                writer.writeheader()
                writer.writerows(
                    {
                        "source": term.source,
                        "target": term.target,
                        "case_sensitive": str(term.case_sensitive).lower(),
                    }
                    for term in terms
                )
        except OSError as error:
            raise OSError(f"Cannot write glossary CSV file {path}") from error

    @staticmethod
    def _term_from_row(
        row: dict[str, str | None],
        source_language: str,
        target_language: str,
        line_number: int,
    ) -> GlossaryTerm:
        raw_case_sensitive = (row.get("case_sensitive") or "").strip().casefold()
        if raw_case_sensitive in {"", "0", "false", "no"}:
            case_sensitive = False
        elif raw_case_sensitive in {"1", "true", "yes"}:
            case_sensitive = True
        else:
            raise ValueError(
                f"Invalid case_sensitive value at glossary CSV line {line_number}"
            )
        try:
            return GlossaryTerm(
                source_language,
                target_language,
                row.get("source") or "",
                row.get("target") or "",
                case_sensitive,
            )
        except ValueError as error:
            raise ValueError(f"Invalid glossary CSV row at line {line_number}: {error}") from error
