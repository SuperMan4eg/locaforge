import json
from pathlib import Path

import pytest

from locaforge.application.dto.project_description import ProjectDescriptionResponse
from locaforge.application.dto.review import ReviewResponse, ReviewResult
from locaforge.application.dto.translation import (
    TranslationRequest,
    TranslationResponse,
    TranslationResult,
)
from locaforge.application.dto.validation import ValidationCode, ValidationIssue
from locaforge.application.errors import NoOpenProjectError
from locaforge.application.ports.project_metadata_lookup import ProjectMetadataLookup
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.domain.entry import EntryStatus
from locaforge.domain.glossary import GlossaryTerm
from locaforge.domain.project_profile import ProjectProfile
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
        self.description_requests = []

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

    def review(self, request):
        return ReviewResponse(
            tuple(
                ReviewResult(item.entry_id, "Improve wording", "Reviewer version")
                for item in request.entries
            )
        )

    def describe_project(self, request):
        self.description_requests.append(request)
        return ProjectDescriptionResponse(
            ProjectProfile(
                description=f"Generated profile for {request.name}",
                project_type="Application",
            )
        )


def make_workspace(
    tmp_path: Path,
    llm_client: StubLlmClient | None = None,
    translation_memory: SQLiteTranslationMemory | None = None,
    glossary: SQLiteGlossary | None = None,
    glossary_csv_format: CsvGlossaryFormat | None = None,
    project_metadata_lookup: ProjectMetadataLookup | None = None,
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
        project_metadata_lookup=project_metadata_lookup,
    )


def test_workspace_generates_project_profile_without_open_project(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path, StubLlmClient())

    profile = workspace.generate_project_profile("Nebula")

    assert profile.description == "Generated profile for Nebula"
    assert profile.project_type == "Application"


def test_workspace_resolves_global_settings_until_project_override_is_enabled(
    tmp_path: Path,
) -> None:
    workspace = make_workspace(tmp_path)
    workspace.create_project(tmp_path / "project.lfproj", "Demo", "en", "ru")
    global_settings = ModelSettings(model="global-model", batch_size=3)
    workspace.set_global_model_settings(global_settings)

    assert workspace.resolve_model_settings() == global_settings
    assert workspace.model_settings_source == "global"

    workspace.set_model_settings_override_enabled(True)
    workspace.set_global_model_settings(ModelSettings(model="new-global-model"))

    assert workspace.resolve_model_settings() == global_settings
    assert workspace.model_settings_source == "project"


def test_workspace_uses_online_context_only_when_requested(tmp_path: Path) -> None:
    class Lookup:
        def lookup(self, project_name: str) -> str:
            return f"Online context for {project_name}"

    llm = StubLlmClient()
    workspace = make_workspace(tmp_path, llm, project_metadata_lookup=Lookup())

    workspace.generate_project_profile("Nebula", use_online_lookup=True)

    assert llm.description_requests[-1].research_context == "Online context for Nebula"


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


def test_workspace_can_select_model_or_reviewer_translation(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    workspace = make_workspace(tmp_path, StubLlmClient())
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_id = project.entries[0].id
    workspace.translate_entries((entry_id,))
    workspace.review_entries((entry_id,))

    selected = workspace.select_translation_candidate(entry_id, "reviewer")

    assert selected.translation == "Reviewer version"
    assert selected.model_translation == "Translated Hello"
    assert selected.reviewer_translation == "Reviewer version"
    assert selected.status is EntryStatus.NEEDS_REVIEW


def test_workspace_undoes_and_redoes_ai_review_results(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    workspace = make_workspace(tmp_path, StubLlmClient())
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_id = project.entries[0].id
    workspace.edit_translation(entry_id, "Translation")

    workspace.review_entries((entry_id,))
    assert workspace.next_undo_operation_label() == "Review translations"
    assert workspace.project.get_entry(entry_id).reviewer_translation == "Reviewer version"
    assert workspace.validation_issues()

    workspace.undo_last_translation()
    assert workspace.project.get_entry(entry_id).reviewer_translation is None
    assert workspace.validation_issues() == ()

    workspace.redo_last_translation()
    assert workspace.project.get_entry(entry_id).reviewer_translation == "Reviewer version"
    assert workspace.validation_issues()


def test_cancelled_ai_review_records_completed_batches_for_undo(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"first": "First", "second": "Second"}', encoding="utf-8")
    workspace = make_workspace(tmp_path, StubLlmClient())
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_ids = tuple(entry.id for entry in project.entries)
    for entry_id in entry_ids:
        workspace.edit_translation(entry_id, f"Translation {entry_id}")
    workspace.update_model_settings(ModelSettings(batch_size=1))
    cancel = {"requested": False}

    result = workspace.review_entries(
        entry_ids,
        progress_callback=lambda completed, _total: cancel.update(
            requested=completed == 1
        ),
        cancellation_check=lambda: cancel["requested"],
    )

    assert result.cancelled is True
    assert result.reviewed_entries == 1
    assert workspace.project.get_entry(entry_ids[0]).reviewer_translation is not None
    assert workspace.project.get_entry(entry_ids[1]).reviewer_translation is None

    restored = workspace.undo_last_translation()
    assert tuple(entry.id for entry in restored) == (entry_ids[0],)
    assert workspace.project.get_entry(entry_ids[0]).reviewer_translation is None


def test_workspace_undoes_and_redoes_dismissed_ai_review_issue(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    workspace = make_workspace(tmp_path, StubLlmClient())
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_id = project.entries[0].id
    workspace.edit_translation(entry_id, "Translation")
    workspace.review_entries((entry_id,))

    workspace.dismiss_ai_review_issue(entry_id)
    assert workspace.validation_issues() == ()
    assert workspace.next_undo_operation_label() == "Dismiss AI review issue"

    workspace.undo_last_translation()
    assert workspace.validation_issues()
    workspace.redo_last_translation()
    assert workspace.validation_issues() == ()


def test_workspace_undoes_bulk_dismissed_ai_review_issues_atomically(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"first": "First", "second": "Second"}', encoding="utf-8")
    workspace = make_workspace(tmp_path, StubLlmClient())
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_ids = tuple(entry.id for entry in project.entries)
    for entry_id in entry_ids:
        workspace.edit_translation(entry_id, f"Translation {entry_id}")
    workspace.review_entries(entry_ids)

    assert workspace.dismiss_ai_review_issues(entry_ids) == 2
    assert workspace.validation_issues() == ()
    assert workspace.next_undo_operation_label() == "Dismiss AI review issues"

    restored = workspace.undo_last_translation()
    assert {entry.id for entry in restored} == set(entry_ids)
    assert len(workspace.validation_issues()) == 2


def test_workspace_refuses_undo_when_validation_changed_after_operation(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    workspace = make_workspace(tmp_path, StubLlmClient())
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_id = project.entries[0].id
    workspace.edit_translation(entry_id, "Translation")
    workspace.review_entries((entry_id,))
    workspace.dismiss_ai_review_issue(entry_id)
    repository = workspace._repository()
    repository.replace_validation_issues(
        project.id,
        entry_id,
        (ValidationIssue(ValidationCode.GLOSSARY_MISMATCH, "Newer QA result"),),
    )

    assert workspace.can_undo_last_translation() is False
    with pytest.raises(ValueError, match="validation results changed later"):
        workspace.undo_last_translation()


def test_workspace_undoes_a_whole_translation_batch_and_restores_qa(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text(
        '{"first": "First", "second": "Second"}', encoding="utf-8"
    )
    workspace = make_workspace(tmp_path, StubLlmClient())
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    first_id, second_id = (entry.id for entry in project.entries)
    workspace.edit_translation(first_id, "")
    issues_before = workspace.validation_issues()

    workspace.translate_entries((first_id, second_id))
    restored = workspace.undo_last_translation()

    assert {entry.id for entry in restored} == {first_id, second_id}
    assert workspace.project.get_entry(first_id).translation == ""
    assert workspace.project.get_entry(first_id).status is EntryStatus.ERROR
    assert workspace.project.get_entry(second_id).translation is None
    assert workspace.project.get_entry(second_id).status is EntryStatus.UNTRANSLATED
    assert workspace.validation_issues() == issues_before
    assert workspace.can_undo_last_translation() is True
    workspace.undo_last_translation()
    assert workspace.project.get_entry(first_id).translation is None


def test_translation_undo_survives_save_and_reopen(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    project_path = tmp_path / "dialog.lfproj"
    workspace = make_workspace(tmp_path, StubLlmClient())
    project = workspace.create_from_json(source_path, project_path, "en", "ru")
    workspace.translate_entries((project.entries[0].id,))
    workspace.save()

    reopened = make_workspace(tmp_path / "reopened", StubLlmClient())
    reopened.open(project_path)
    reopened.undo_last_translation()

    assert reopened.project.entries[0].translation is None
    assert reopened.project.entries[0].model_translation is None


def test_workspace_redoes_undone_translation_with_validation_state(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    workspace = make_workspace(tmp_path, StubLlmClient())
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_id = project.entries[0].id
    workspace.translate_entries((entry_id,))
    translated = workspace.project.get_entry(entry_id).translation

    workspace.undo_last_translation()
    assert workspace.can_redo_last_translation() is True
    restored = workspace.redo_last_translation()

    assert restored[0].translation == translated
    assert restored[0].model_translation == translated
    assert workspace.can_redo_last_translation() is False
    assert workspace.can_undo_last_translation() is True


def test_translation_redo_survives_save_and_reopen(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    project_path = tmp_path / "dialog.lfproj"
    workspace = make_workspace(tmp_path, StubLlmClient())
    project = workspace.create_from_json(source_path, project_path, "en", "ru")
    workspace.translate_entries((project.entries[0].id,))
    workspace.undo_last_translation()
    workspace.save()

    reopened = make_workspace(tmp_path / "reopened", StubLlmClient())
    reopened.open(project_path)
    reopened.redo_last_translation()

    assert reopened.project.entries[0].translation == "Translated Hello"


def test_manual_edit_after_undo_disables_translation_redo(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    workspace = make_workspace(tmp_path, StubLlmClient())
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_id = project.entries[0].id
    workspace.translate_entries((entry_id,))
    workspace.undo_last_translation()

    workspace.edit_translation(entry_id, "Manual")

    assert workspace.can_redo_last_translation() is False
    with pytest.raises(ValueError, match="no translation operation to redo"):
        workspace.redo_last_translation()


def test_manual_edit_is_undoable_before_earlier_batch_operation(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    workspace = make_workspace(tmp_path, StubLlmClient())
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_id = project.entries[0].id
    workspace.translate_entries((entry_id,))
    workspace.edit_translation(entry_id, "Manual edit")

    assert workspace.can_undo_last_translation() is True
    workspace.undo_last_translation()
    assert workspace.project.get_entry(entry_id).translation == "Translated Hello"
    workspace.undo_last_translation()
    assert workspace.project.get_entry(entry_id).translation is None


def test_manual_edit_undo_and_redo_restore_validation_state(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello {name}"}', encoding="utf-8")
    workspace = make_workspace(tmp_path)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_id = project.entries[0].id

    workspace.edit_translation(entry_id, "Broken")
    assert workspace.project.get_entry(entry_id).status is EntryStatus.ERROR
    assert workspace.validation_issues()
    workspace.undo_last_translation()
    assert workspace.project.get_entry(entry_id).translation is None
    assert workspace.validation_issues() == ()

    workspace.redo_last_translation()
    assert workspace.project.get_entry(entry_id).translation == "Broken"
    assert workspace.project.get_entry(entry_id).status is EntryStatus.ERROR
    assert workspace.validation_issues()


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
    assert workspace.next_undo_operation_label() == "Replace translations"

    workspace.undo_last_translation()
    assert workspace.project.get_entry(first_entry.id).translation == "Old first"
    assert workspace.project.get_entry(second_entry.id).translation == "Old second"


def test_workspace_undoes_apply_translation_to_matches_atomically(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text(
        '{"first": "Same", "second": "Same", "other": "Other"}',
        encoding="utf-8",
    )
    workspace = make_workspace(tmp_path)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    first_id, second_id, other_id = (entry.id for entry in project.entries)
    workspace.edit_translation(first_id, "First translation")
    workspace.edit_translation(second_id, "Second translation")

    assert workspace.apply_translation_to_matches(first_id, "Shared") == (
        first_id,
        second_id,
    )
    assert workspace.next_undo_operation_label() == "Apply translation to matches"
    workspace.undo_last_translation()

    assert workspace.project.get_entry(first_id).translation == "First translation"
    assert workspace.project.get_entry(second_id).translation == "Second translation"
    assert workspace.project.get_entry(other_id).translation is None


def test_workspace_stores_approved_edit_and_exposes_memory_match(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    workspace = make_workspace(tmp_path, translation_memory=memory)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )

    workspace.edit_translation(project.entries[0].id, "Привет")

    assert workspace.translation_memory_match(project.entries[0].id) is None

    workspace.set_entry_approval(project.entries[0].id, True)

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


def test_workspace_undoes_and_redoes_review_and_lock_actions(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    workspace = make_workspace(tmp_path)
    project = workspace.create_from_json(
        source_path, tmp_path / "dialog.lfproj", "en", "ru"
    )
    entry_id = project.entries[0].id
    workspace.edit_translation(entry_id, "Translation")
    assert workspace.next_undo_operation_label() == "Edit translation"
    workspace.set_entry_approval(entry_id, True)
    assert workspace.next_undo_operation_label() == "Approve translation"
    workspace.set_entry_locked(entry_id, True)
    assert workspace.next_undo_operation_label() == "Lock translation"

    workspace.undo_last_translation()
    assert workspace.next_redo_operation_label() == "Lock translation"
    assert workspace.next_undo_operation_label() == "Approve translation"
    assert workspace.project.get_entry(entry_id).status is EntryStatus.APPROVED
    assert workspace.project.get_entry(entry_id).locked is False

    workspace.undo_last_translation()
    assert workspace.project.get_entry(entry_id).status is EntryStatus.NEEDS_REVIEW
    assert workspace.project.get_entry(entry_id).locked is False

    workspace.redo_last_translation()
    workspace.redo_last_translation()
    assert workspace.project.get_entry(entry_id).status is EntryStatus.APPROVED
    assert workspace.project.get_entry(entry_id).locked is True
    assert workspace.next_redo_operation_label() is None


def test_workspace_undoes_bulk_review_actions_atomically(tmp_path: Path) -> None:
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
        workspace.edit_translation(entry_id, f"Translation {entry_id}")
    workspace.set_entries_approval(entry_ids, True)
    workspace.set_entries_locked(entry_ids, True)

    assert {entry.id for entry in workspace.undo_last_translation()} == set(entry_ids)
    assert all(not workspace.project.get_entry(entry_id).locked for entry_id in entry_ids)
    assert all(
        workspace.project.get_entry(entry_id).status is EntryStatus.APPROVED
        for entry_id in entry_ids
    )

    assert {entry.id for entry in workspace.undo_last_translation()} == set(entry_ids)
    assert all(
        workspace.project.get_entry(entry_id).status is EntryStatus.NEEDS_REVIEW
        for entry_id in entry_ids
    )


def test_review_action_undo_survives_save_and_reopen(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.json"
    source_path.write_text('{"text": "Hello"}', encoding="utf-8")
    project_path = tmp_path / "dialog.lfproj"
    workspace = make_workspace(tmp_path)
    project = workspace.create_from_json(source_path, project_path, "en", "ru")
    entry_id = project.entries[0].id
    workspace.edit_translation(entry_id, "Translation")
    workspace.set_entry_approval(entry_id, True)
    workspace.set_entry_locked(entry_id, True)
    workspace.save()

    reopened = make_workspace(tmp_path / "reopened")
    reopened.open(project_path)
    reopened.undo_last_translation()

    entry = reopened.project.get_entry(entry_id)
    assert entry.status is EntryStatus.APPROVED
    assert entry.locked is False


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
    assert workspace.next_undo_operation_label() == "Restore translation revision"
    workspace.undo_last_translation()
    assert workspace.project.get_entry(entry_id).translation == "Здравствуйте"


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
