from pathlib import Path

import pytest

from locaforge.application.services.terminology import TerminologyService
from locaforge.domain.glossary import GlossaryTerm
from locaforge.domain.project import Project
from locaforge.domain.translation_memory import TranslationMemoryRecord


class MemoryStore:
    def __init__(self) -> None:
        self.records: list[TranslationMemoryRecord] = []

    def store(self, record: TranslationMemoryRecord) -> None:
        self.records.append(record)

    def delete(self, record: TranslationMemoryRecord) -> None:
        self.records.remove(record)

    def list_records(
        self, source_language: str = "", target_language: str = "", search: str = ""
    ) -> tuple[TranslationMemoryRecord, ...]:
        return tuple(
            record
            for record in self.records
            if (not source_language or record.source_language == source_language)
            and (not target_language or record.target_language == target_language)
            and (not search or search in record.source)
        )

    def find_exact(self, *_args: object, **_kwargs: object) -> None:
        return None

    def find_similar(self, *_args: object, **_kwargs: object) -> tuple[()]:
        return ()


class Glossary:
    def __init__(self) -> None:
        self.terms: list[GlossaryTerm] = []

    def store(self, term: GlossaryTerm) -> None:
        self.terms.append(term)

    def remove(self, term: GlossaryTerm) -> None:
        self.terms.remove(term)

    def list_terms(
        self, source_language: str, target_language: str
    ) -> tuple[GlossaryTerm, ...]:
        return tuple(
            term
            for term in self.terms
            if term.source_language == source_language
            and term.target_language == target_language
        )

    def find_for_sources(self, *_args: object) -> tuple[()]:
        return ()


class GlossaryCsv:
    def __init__(self, imported: tuple[GlossaryTerm, ...] = ()) -> None:
        self.imported = imported
        self.exported: tuple[tuple[GlossaryTerm, ...], Path] | None = None

    def import_file(
        self, _path: Path, _source_language: str, _target_language: str
    ) -> tuple[GlossaryTerm, ...]:
        return self.imported

    def export_file(self, terms: tuple[GlossaryTerm, ...], path: Path) -> None:
        self.exported = terms, path


def make_project() -> Project:
    return Project("project-1", "Demo", "en", "ru")


def test_manages_translation_memory_records() -> None:
    memory = MemoryStore()
    service = TerminologyService(memory, None, None)
    record = TranslationMemoryRecord("en", "ru", "Save", "Сохранить")

    service.store_translation_memory_record(record)

    assert service.translation_memory_records("en", "ru", "Sav") == (record,)
    service.delete_translation_memory_record(record)
    assert service.translation_memory_records() == ()


def test_manages_only_current_project_glossary_terms() -> None:
    glossary = Glossary()
    glossary.store(GlossaryTerm("en", "de", "Save", "Speichern"))
    service = TerminologyService(None, glossary, None)
    project = make_project()

    term = service.store_glossary_term(project, "Save", "Сохранить", True)

    assert service.glossary_terms(project) == (term,)
    with pytest.raises(ValueError, match="another language pair"):
        service.remove_glossary_term(
            project, GlossaryTerm("en", "de", "Save", "Speichern")
        )
    service.remove_glossary_term(project, term)
    assert service.glossary_terms(project) == ()


def test_imports_and_exports_current_language_pair(tmp_path: Path) -> None:
    term = GlossaryTerm("en", "ru", "Save", "Сохранить")
    glossary = Glossary()
    csv_format = GlossaryCsv((term,))
    service = TerminologyService(None, glossary, csv_format)
    project = make_project()

    assert service.import_glossary_csv(project, tmp_path / "in.csv") == 1
    destination = tmp_path / "out.csv"
    service.export_glossary_csv(project, destination)

    assert csv_format.exported == ((term,), destination)


def test_optional_stores_have_explicit_absent_behavior(tmp_path: Path) -> None:
    service = TerminologyService(None, None, None)
    project = make_project()
    record = TranslationMemoryRecord("en", "ru", "Save", "Сохранить")

    assert service.translation_memory_records() == ()
    assert service.glossary_terms(project) == ()
    with pytest.raises(RuntimeError, match="Translation memory"):
        service.store_translation_memory_record(record)
    with pytest.raises(RuntimeError, match="No glossary"):
        service.store_glossary_term(project, "Save", "Сохранить")
    with pytest.raises(RuntimeError, match="Glossary CSV"):
        service.import_glossary_csv(project, tmp_path / "terms.csv")
