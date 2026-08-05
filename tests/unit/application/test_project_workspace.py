import json
from pathlib import Path

import pytest

from locaforge.application.dto.translation import (
    TranslationRequest,
    TranslationResponse,
    TranslationResult,
)
from locaforge.application.errors import NoOpenProjectError
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.entry import EntryStatus
from locaforge.domain.glossary import GlossaryTerm
from locaforge.domain.settings import ModelSettings
from locaforge.infrastructure.formats.glossary_csv import CsvGlossaryFormat
from locaforge.infrastructure.formats.json_format import JsonFileExporter, JsonFileImporter
from locaforge.infrastructure.persistence.lfproj_container import LfprojContainer
from locaforge.infrastructure.persistence.sqlite_glossary import SQLiteGlossary
from locaforge.infrastructure.persistence.sqlite_project_repository_factory import (
    SQLiteProjectRepositoryFactory,
)
from locaforge.infrastructure.persistence.sqlite_translation_memory import (
    SQLiteTranslationMemory,
)


class StubLlmClient:
    def __init__(self) -> None:
        self.requests: list[TranslationRequest] = []

    def health_check(self) -> bool:
        return True

    def list_models(self) -> tuple[str, ...]:
        return ("model-a", "model-b")

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        self.requests.append(request)
        return TranslationResponse(
            tuple(
                TranslationResult(item.entry_id, f"Translated {item.source}")
                for item in request.entries
            )
        )


def make_workspace(
    tmp_path: Path,
    llm_client: StubLlmClient | None = None,
    translation_memory: SQLiteTranslationMemory | None = None,
    glossary: SQLiteGlossary | None = None,
    glossary_csv_format: CsvGlossaryFormat | None = None,
) -> ProjectWorkspace:
    return ProjectWorkspace(
        JsonFileImporter(),
        JsonFileExporter(),
        LfprojContainer(tmp_path / "working"),
        SQLiteProjectRepositoryFactory(),
        llm_client,
        translation_memory,
        glossary,
        glossary_csv_format,
    )


def test_workspace_creates_edits_saves_and_exports_project(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    project_path = tmp_path / "dialog.lfproj"
    workspace = make_workspace(tmp_path)

    project = workspace.create_from_json(source_path, project_path, "en", "ru")
    workspace.edit_translation(project.entries[0].id, "Привет")
    saved = workspace.save()
    destination = tmp_path / "dialog_ru.json"
    workspace.export_json(destination)

    assert saved.dirty is False
    assert json.loads(destination.read_text(encoding="utf-8")) == {"text": "Привет"}


def test_workspace_autosave_writes_a_portable_snapshot(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    project_path = tmp_path / "dialog.lfproj"
    workspace = make_workspace(tmp_path)
    project = workspace.create_from_json(source_path, project_path, "en", "ru")
    workspace.edit_translation(project.entries[0].id, "Привет")

    workspace.autosave()
    workspace.refresh_after_autosave()

    assert workspace.project.dirty is False
    assert project_path.is_file()
    assert not project_path.with_suffix(".lfproj.bak").exists()


def test_workspace_export_preflight_reports_untranslated_and_invalid_entries(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text(
        '{"first": "First", "second": "Second"}', encoding="utf-8"
    )
    workspace = make_workspace(tmp_path)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    workspace.edit_translation(project.entries[0].id, "")

    preflight = workspace.export_preflight()

    assert preflight.untranslated_entries == 1
    assert preflight.entries_with_issues == 1
    assert preflight.has_warnings is True


def test_workspace_reports_project_statistics(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text(
        '{"first": "First", "second": "Second"}', encoding="utf-8"
    )
    workspace = make_workspace(tmp_path)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    first_entry, second_entry = project.entries
    workspace.edit_translation(first_entry.id, "Первый")
    workspace.set_entry_approval(first_entry.id, True)
    workspace.set_entry_locked(first_entry.id, True)
    workspace.edit_translation(second_entry.id, "")

    statistics = workspace.project_statistics()

    assert statistics.total_entries == 2
    assert statistics.translated_entries == 2
    assert statistics.untranslated_entries == 0
    assert statistics.approved_entries == 1
    assert statistics.error_entries == 1
    assert statistics.locked_entries == 1
    assert statistics.entries_with_issues == 1
    assert statistics.completion_percent == 100


def test_workspace_lists_only_untranslated_entry_ids(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text(
        '{"first": "First", "second": "Second"}', encoding="utf-8"
    )
    workspace = make_workspace(tmp_path)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )

    workspace.edit_translation(project.entries[0].id, "Первый")

    assert workspace.untranslated_entry_ids() == (project.entries[1].id,)


def test_workspace_lists_only_unlocked_needs_review_entries(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text(
        '{"first": "First", "second": "Second", "third": "Third"}',
        encoding="utf-8",
    )
    workspace = make_workspace(tmp_path)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    first_entry, second_entry, _third_entry = project.entries
    workspace.edit_translation(first_entry.id, "Первый")
    workspace.set_entry_approval(first_entry.id, True)
    workspace.set_entry_locked(first_entry.id, True)
    workspace.edit_translation(second_entry.id, "Второй")

    assert workspace.reviewable_entry_ids() == (second_entry.id,)


def test_workspace_can_cancel_ai_review_before_next_batch(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    workspace = make_workspace(tmp_path, llm_client=StubLlmClient())
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    workspace.edit_translation(project.entries[0].id, "Привет")

    result = workspace.review_entries(
        (project.entries[0].id,), cancellation_check=lambda: True
    )

    assert result.cancelled is True
    assert result.reviewed_entries == 0


def test_workspace_replaces_text_in_unlocked_translations(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text(
        '{"first": "First", "second": "Second"}', encoding="utf-8"
    )
    workspace = make_workspace(tmp_path)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    first_entry, second_entry = project.entries
    workspace.edit_translation(first_entry.id, "Old first")
    workspace.edit_translation(second_entry.id, "Old second")
    workspace.set_entry_locked(second_entry.id, True)

    assert workspace.replace_translations("Old", "New") == (first_entry.id,)
    assert workspace.project.get_entry(first_entry.id).translation == "New first"
    assert workspace.project.get_entry(second_entry.id).translation == "Old second"


def test_workspace_stores_manual_edit_and_exposes_memory_match(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    workspace = make_workspace(tmp_path, translation_memory=memory)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )

    workspace.edit_translation(project.entries[0].id, "Привет")

    match = workspace.translation_memory_match(project.entries[0].id)
    assert match is not None
    assert match.translation == "Привет"
    matches = workspace.translation_memory_matches(project.entries[0].id)
    assert matches[0].record == match
    assert matches[0].score == 1.0


def test_workspace_requires_an_open_project(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)

    with pytest.raises(NoOpenProjectError):
        workspace.save()


def test_workspace_manages_glossary_for_current_language_pair(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Save"}', encoding="utf-8")
    glossary = SQLiteGlossary(tmp_path / "glossary.db")
    glossary.store(GlossaryTerm("en", "de", "Save", "Speichern"))
    workspace = make_workspace(tmp_path, glossary=glossary)
    workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )

    term = workspace.store_glossary_term("Save", "Сохранить")

    assert workspace.glossary_terms() == (term,)
    workspace.remove_glossary_term(term)
    assert workspace.glossary_terms() == ()
    assert glossary.list_terms("en", "de") == (
        GlossaryTerm("en", "de", "Save", "Speichern"),
    )


def test_workspace_imports_and_exports_glossary_csv(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Save"}', encoding="utf-8")
    input_path = tmp_path / "terms.csv"
    input_path.write_text(
        "source,target,case_sensitive\nSave,Сохранить,false\n", encoding="utf-8"
    )
    glossary = SQLiteGlossary(tmp_path / "glossary.db")
    workspace = make_workspace(
        tmp_path,
        glossary=glossary,
        glossary_csv_format=CsvGlossaryFormat(),
    )
    workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )

    assert workspace.import_glossary_csv(input_path) == 1
    output_path = tmp_path / "exported.csv"
    workspace.export_glossary_csv(output_path)

    assert CsvGlossaryFormat().import_file(output_path, "en", "ru") == (
        GlossaryTerm("en", "ru", "Save", "Сохранить"),
    )


def test_workspace_manages_entry_review_and_lock_state(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    workspace = make_workspace(tmp_path)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_id = project.entries[0].id
    workspace.edit_translation(entry_id, "Привет")

    workspace.set_entry_approval(entry_id, True)
    workspace.set_entry_locked(entry_id, True)

    assert workspace.project.get_entry(entry_id).status is EntryStatus.APPROVED
    assert workspace.project.get_entry(entry_id).locked is True

    workspace.set_entry_approval(entry_id, False)
    workspace.set_entry_locked(entry_id, False)
    assert workspace.project.get_entry(entry_id).status is EntryStatus.NEEDS_REVIEW
    assert workspace.project.get_entry(entry_id).locked is False


def test_workspace_applies_review_actions_to_multiple_entries(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text(
        '{"first": "First", "second": "Second"}', encoding="utf-8"
    )
    workspace = make_workspace(tmp_path)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_ids = tuple(entry.id for entry in project.entries)
    for entry_id in entry_ids:
        workspace.edit_translation(entry_id, f"Перевод {entry_id}")

    assert workspace.set_entries_approval(entry_ids, True) == entry_ids
    assert workspace.set_entries_locked(entry_ids, True) == entry_ids
    assert all(
        workspace.project.get_entry(entry_id).status is EntryStatus.APPROVED
        and workspace.project.get_entry(entry_id).locked
        for entry_id in entry_ids
    )


def test_workspace_lists_and_restores_entry_history(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    workspace = make_workspace(tmp_path)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_id = project.entries[0].id
    workspace.edit_translation(entry_id, "Привет")
    workspace.edit_translation(entry_id, "Здравствуйте")

    revision = workspace.entry_revisions(entry_id)[0]
    workspace.restore_entry_revision(entry_id, revision.revision_id)

    assert workspace.project.get_entry(entry_id).translation == "Привет"


def test_workspace_translates_selected_entries(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    workspace = make_workspace(tmp_path, StubLlmClient())
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )

    result = workspace.translate_entries((project.entries[0].id,), "test-model")

    assert result.translated_entry_ids == (project.entries[0].id,)
    assert workspace.project.entries[0].translation == "Translated Hello"
    assert workspace.project.dirty is True


def test_workspace_persists_settings_and_applies_batch_size_and_prompt(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text(
        '{"one": "First", "two": "Second", "three": "Third"}', encoding="utf-8"
    )
    llm_client = StubLlmClient()
    workspace = make_workspace(tmp_path, llm_client)
    project_path = tmp_path / "dialog.lfproj"
    project = workspace.create_from_json(source_path, project_path, "en", "ru")
    settings = ModelSettings(
        model="model-b",
        timeout_seconds=45.0,
        batch_size=2,
        system_prompt="Use a concise UI style.",
    )

    workspace.update_model_settings(settings)
    result = workspace.translate_entries(tuple(entry.id for entry in project.entries))
    workspace.save()

    assert workspace.list_models() == ("model-a", "model-b")
    assert len(llm_client.requests) == 2
    assert all(request.model == "model-b" for request in llm_client.requests)
    assert all(request.timeout_seconds == 45.0 for request in llm_client.requests)
    assert llm_client.requests[0].prompt.startswith("Use a concise UI style.")
    assert len(result.translated_entry_ids) == 3

    reopened = make_workspace(tmp_path, StubLlmClient())
    reopened.open(project_path)
    assert reopened.project.model_settings == settings


def test_workspace_reports_progress_and_cancels_between_batches(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text(
        '{"one": "First", "two": "Second", "three": "Third"}', encoding="utf-8"
    )
    llm_client = StubLlmClient()
    workspace = make_workspace(tmp_path, llm_client)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    workspace.update_model_settings(ModelSettings(batch_size=1))
    progress_updates: list[tuple[int, int]] = []
    cancellation = {"requested": False}

    def report_progress(completed: int, total: int) -> None:
        progress_updates.append((completed, total))
        if completed == 1:
            cancellation["requested"] = True

    result = workspace.translate_entries(
        tuple(entry.id for entry in project.entries),
        progress_callback=report_progress,
        cancellation_check=lambda: cancellation["requested"],
    )

    assert result.cancelled is True
    assert len(result.translated_entry_ids) == 1
    assert len(llm_client.requests) == 1
    assert progress_updates == [(0, 3), (1, 3)]
