from __future__ import annotations

from pathlib import Path

from locaforge.application.use_cases.find_translation_memory_matches import (
    FindTranslationMemoryMatches,
)
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.project import Project
from locaforge.domain.translation_memory import TranslationMemoryRecord
from locaforge.infrastructure.persistence.sqlite_project_repository import (
    SQLiteProjectRepository,
)
from locaforge.infrastructure.persistence.sqlite_translation_memory import (
    SQLiteTranslationMemory,
)


def test_fuzzy_match_workflow_filters_structurally_unsafe_suggestions(
    tmp_path: Path,
) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = Project(
        id="project-1",
        name="Dialog",
        source_language="en",
        target_language="ru",
        source_document={"text": "Hello {name}"},
        entries=[TranslationEntry("entry-1", ("text",), "Hello {name}")],
    )
    repository.create(project)
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    safe = TranslationMemoryRecord(
        "en", "ru", "Hello {player}", "Привет {name}"
    )
    memory.store(safe)
    memory.store(TranslationMemoryRecord("en", "ru", "Hello user", "Привет"))

    matches = FindTranslationMemoryMatches(repository, memory).execute(
        project.id, "entry-1", minimum_score=0.5
    )

    assert [match.record for match in matches] == [safe]


def test_fuzzy_match_workflow_respects_requested_limit(tmp_path: Path) -> None:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    project = Project(
        id="project-1",
        name="Dialog",
        source_language="en",
        target_language="ru",
        source_document={"text": "Start game"},
        entries=[TranslationEntry("entry-1", ("text",), "Start game")],
    )
    repository.create(project)
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    memory.store(TranslationMemoryRecord("en", "ru", "Start game", "Начать игру"))
    memory.store(
        TranslationMemoryRecord("en", "ru", "Start new game", "Начать новую игру")
    )

    matches = FindTranslationMemoryMatches(repository, memory).execute(
        project.id, "entry-1", limit=1
    )

    assert len(matches) == 1
    assert matches[0].record.source == "Start game"
