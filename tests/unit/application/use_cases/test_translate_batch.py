from pathlib import Path

from locaforge.application.dto.translation import (
    TranslationRequest,
    TranslationResponse,
    TranslationResult,
)
from locaforge.application.dto.validation import ValidationCode
from locaforge.application.errors import InvalidModelResponseError, ModelUnavailableError
from locaforge.application.use_cases.translate_batch import TranslateBatch
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.glossary import GlossaryTerm
from locaforge.domain.project import Project
from locaforge.domain.translation_memory import TranslationMemoryRecord
from locaforge.infrastructure.persistence.sqlite_glossary import SQLiteGlossary
from locaforge.infrastructure.persistence.sqlite_project_repository import SQLiteProjectRepository
from locaforge.infrastructure.persistence.sqlite_translation_memory import (
    SQLiteTranslationMemory,
)


class StubLlmClient:
    def __init__(self, response: TranslationResponse) -> None:
        self.response = response

    def health_check(self) -> bool:
        return True

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        return self.response


class CountingLlmClient(StubLlmClient):
    def __init__(self, response: TranslationResponse) -> None:
        super().__init__(response)
        self.calls = 0
        self.last_request: TranslationRequest | None = None

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        self.calls += 1
        self.last_request = request
        return super().translate(request)


class PlaceholderAwareLlmClient:
    def __init__(self) -> None:
        self.last_request: TranslationRequest | None = None

    def health_check(self) -> bool:
        return True

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        self.last_request = request
        source = request.entries[0].source
        return TranslationResponse(
            (TranslationResult("entry-1", source.replace("Hello", "Привет")),)
        )


class TransientFailureLlmClient:
    def __init__(self) -> None:
        self.calls = 0

    def health_check(self) -> bool:
        return True

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        self.calls += 1
        if self.calls == 1:
            raise ModelUnavailableError("temporary failure")
        return TranslationResponse((TranslationResult(request.entries[0].entry_id, "Recovered"),))


class SplitOnlyLlmClient:
    def __init__(self) -> None:
        self.requested_groups: list[tuple[str, ...]] = []

    def health_check(self) -> bool:
        return True

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        entry_ids = tuple(entry.entry_id for entry in request.entries)
        self.requested_groups.append(entry_ids)
        if len(entry_ids) > 1:
            raise InvalidModelResponseError("batch rejected")
        return TranslationResponse((TranslationResult(entry_ids[0], f"Translated {entry_ids[0]}"),))


class CancellingPartialLlmClient:
    def __init__(self, cancellation: dict[str, bool]) -> None:
        self._cancellation = cancellation
        self.calls = 0

    def health_check(self) -> bool:
        return True

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        self.calls += 1
        self._cancellation["requested"] = True
        first_entry = request.entries[0]
        return TranslationResponse(
            (TranslationResult(first_entry.entry_id, f"Translated {first_entry.source}"),)
        )


def make_repository(tmp_path: Path) -> SQLiteProjectRepository:
    repository = SQLiteProjectRepository(tmp_path / "project.db")
    repository.create(
        Project(
            id="project-1",
            name="Dialog",
            source_language="en",
            target_language="ru",
            source_document={"one": "Hello", "two": "Locked", "three": "Approved"},
            entries=[
                TranslationEntry("entry-1", ("one",), "Hello"),
                TranslationEntry(
                    "entry-2",
                    ("two",),
                    "Locked",
                    translation="Заблокировано",
                    status=EntryStatus.TRANSLATED,
                    locked=True,
                ),
                TranslationEntry(
                    "entry-3",
                    ("three",),
                    "Approved",
                    translation="Одобрено",
                    status=EntryStatus.APPROVED,
                ),
            ],
        )
    )
    return repository


def test_translates_eligible_entries_and_skips_locked_or_approved(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    service = TranslateBatch(
        repository,
        StubLlmClient(TranslationResponse((TranslationResult("entry-1", "Привет"),))),
    )

    result = service.execute("project-1", ("entry-1", "entry-2", "entry-3"), "qwen3")

    assert result.translated_entry_ids == ("entry-1",)
    assert result.skipped_entry_ids == ("entry-2", "entry-3")
    assert not result.errors
    assert repository.get_entry("project-1", "entry-1").status is EntryStatus.TRANSLATED


def test_reuses_one_model_translation_for_identical_source_and_context(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    project = repository.get("project-1")
    project.add_entry(TranslationEntry("entry-4", ("four",), "Hello"))
    repository.save(project)
    llm_client = CountingLlmClient(
        TranslationResponse((TranslationResult("entry-1", "Привет"),))
    )

    result = TranslateBatch(repository, llm_client).execute(
        "project-1", ("entry-1", "entry-4"), "qwen3"
    )

    assert llm_client.calls == 1
    assert llm_client.last_request is not None
    assert tuple(item.entry_id for item in llm_client.last_request.entries) == ("entry-1",)
    assert result.translated_entry_ids == ("entry-1", "entry-4")
    assert repository.get_entry("project-1", "entry-4").translation == "Привет"


def test_uses_exact_translation_memory_match_without_calling_model(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    memory.store(TranslationMemoryRecord("en", "ru", "Hello", "Привет"))
    llm_client = CountingLlmClient(TranslationResponse(()))

    result = TranslateBatch(
        repository,
        llm_client,
        translation_memory=memory,
    ).execute("project-1", ("entry-1",), "qwen3")

    assert result.translated_entry_ids == ("entry-1",)
    assert llm_client.calls == 0
    assert repository.get_entry("project-1", "entry-1").translation == "Привет"


def test_stores_valid_model_translation_in_translation_memory(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    llm_client = CountingLlmClient(
        TranslationResponse((TranslationResult("entry-1", "Привет"),))
    )

    result = TranslateBatch(
        repository,
        llm_client,
        translation_memory=memory,
    ).execute("project-1", ("entry-1",), "qwen3")

    assert result.translated_entry_ids == ("entry-1",)
    assert llm_client.calls == 1
    assert memory.find_exact("en", "ru", "Hello") == TranslationMemoryRecord(
        "en", "ru", "Hello", "Привет"
    )


def test_injects_relevant_glossary_terms_into_model_prompt(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    glossary = SQLiteGlossary(tmp_path / "glossary.db")
    glossary.store(GlossaryTerm("en", "ru", "Hello", "Здравствуйте"))
    glossary.store(GlossaryTerm("en", "ru", "Exit", "Выход"))
    llm_client = CountingLlmClient(
        TranslationResponse((TranslationResult("entry-1", "Здравствуйте"),))
    )

    result = TranslateBatch(
        repository,
        llm_client,
        glossary=glossary,
    ).execute("project-1", ("entry-1",), "qwen3")

    assert result.translated_entry_ids == ("entry-1",)
    assert llm_client.last_request is not None
    assert "Required terminology" in llm_client.last_request.prompt
    assert '"source": "Hello"' in llm_client.last_request.prompt
    assert '"target": "Здравствуйте"' in llm_client.last_request.prompt
    assert '"source": "Exit"' not in llm_client.last_request.prompt


def test_rejects_model_translation_that_violates_glossary(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    glossary = SQLiteGlossary(tmp_path / "glossary.db")
    glossary.store(GlossaryTerm("en", "ru", "Hello", "Здравствуйте"))
    llm_client = CountingLlmClient(
        TranslationResponse((TranslationResult("entry-1", "Привет"),))
    )

    result = TranslateBatch(
        repository,
        llm_client,
        glossary=glossary,
    ).execute("project-1", ("entry-1",), "qwen3")

    assert result.translated_entry_ids == ()
    assert "Required glossary translation" in result.errors[0]
    assert repository.list_validation_issues("project-1")[0].code is (
        ValidationCode.GLOSSARY_MISMATCH
    )


def test_ignores_translation_memory_match_that_violates_glossary(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    glossary = SQLiteGlossary(tmp_path / "glossary.db")
    glossary.store(GlossaryTerm("en", "ru", "Hello", "Здравствуйте"))
    memory = SQLiteTranslationMemory(tmp_path / "tm.db")
    memory.store(TranslationMemoryRecord("en", "ru", "Hello", "Привет"))
    llm_client = CountingLlmClient(
        TranslationResponse((TranslationResult("entry-1", "Здравствуйте"),))
    )

    result = TranslateBatch(
        repository,
        llm_client,
        translation_memory=memory,
        glossary=glossary,
    ).execute("project-1", ("entry-1",), "qwen3")

    assert result.translated_entry_ids == ("entry-1",)
    assert llm_client.calls == 1
    assert repository.get_entry("project-1", "entry-1").translation == "Здравствуйте"


def test_keeps_valid_results_when_batch_response_is_partial(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    project = repository.get("project-1")
    second_entry = TranslationEntry("entry-4", ("four",), "Goodbye")
    project.add_entry(second_entry)
    repository.save(project)
    service = TranslateBatch(
        repository,
        StubLlmClient(
            TranslationResponse(
                (
                    TranslationResult("entry-1", "Привет"),
                    TranslationResult("unknown", "Неизвестно"),
                )
            )
        ),
    )

    result = service.execute("project-1", ("entry-1", "entry-4"), "qwen3")

    assert result.translated_entry_ids == ("entry-1",)
    assert result.errors
    assert repository.get_entry("project-1", "entry-1").translation == "Привет"
    assert repository.get_entry("project-1", "entry-4").translation is None


def test_restores_validated_placeholders_before_persisting_translation(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    project = repository.get("project-1")
    project.entries[0].source = "Hello, {name}!\\nScore: %d <b>points</b>"
    repository.save(project)

    llm_client = PlaceholderAwareLlmClient()
    result = TranslateBatch(repository, llm_client).execute(
        "project-1", ("entry-1",), "qwen3"
    )

    assert not result.errors
    assert llm_client.last_request is not None
    assert "{name}" not in llm_client.last_request.prompt
    assert "__LF_PH_" in llm_client.last_request.prompt
    assert repository.get_entry("project-1", "entry-1").translation == (
        "Привет, {name}!\\nScore: %d <b>points</b>"
    )


def test_rejects_translation_that_loses_a_placeholder(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    project = repository.get("project-1")
    project.entries[0].source = "Hello, {name}!"
    repository.save(project)
    service = TranslateBatch(
        repository,
        StubLlmClient(TranslationResponse((TranslationResult("entry-1", "Привет!"),))),
    )

    result = service.execute("project-1", ("entry-1",), "qwen3")

    assert not result.translated_entry_ids
    assert "Invalid placeholders" in result.errors[0]
    assert repository.get_entry("project-1", "entry-1").translation is None
    assert repository.list_validation_issues("project-1")[0].code is (
        ValidationCode.PLACEHOLDER_MISMATCH
    )


def test_rejects_translation_that_exceeds_entry_length_limit(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    project = repository.get("project-1")
    project.entries[0].max_length = 3
    repository.save(project)
    service = TranslateBatch(
        repository,
        StubLlmClient(TranslationResponse((TranslationResult("entry-1", "Привет"),))),
    )

    result = service.execute("project-1", ("entry-1",), "qwen3")

    assert not result.translated_entry_ids
    assert "exceeds limit" in result.errors[0]
    assert repository.get_entry("project-1", "entry-1").translation is None


def test_retries_a_transient_backend_failure(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    llm_client = TransientFailureLlmClient()

    result = TranslateBatch(repository, llm_client).execute(
        "project-1", ("entry-1",), "qwen3"
    )

    assert result.translated_entry_ids == ("entry-1",)
    assert not result.errors
    assert llm_client.calls == 2


def test_splits_a_repeatedly_failing_batch_into_single_entries(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    project = repository.get("project-1")
    project.add_entry(TranslationEntry("entry-4", ("four",), "Goodbye"))
    repository.save(project)
    llm_client = SplitOnlyLlmClient()

    result = TranslateBatch(repository, llm_client).execute(
        "project-1", ("entry-1", "entry-4"), "qwen3"
    )

    assert result.translated_entry_ids == ("entry-1", "entry-4")
    assert not result.errors
    assert llm_client.requested_groups == [
        ("entry-1", "entry-4"),
        ("entry-1", "entry-4"),
        ("entry-1",),
        ("entry-4",),
    ]


def test_cancellation_stops_retry_after_current_model_response(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    project = repository.get("project-1")
    project.add_entry(TranslationEntry("entry-4", ("four",), "Goodbye"))
    repository.save(project)
    cancellation = {"requested": False}
    llm_client = CancellingPartialLlmClient(cancellation)

    result = TranslateBatch(repository, llm_client).execute(
        "project-1",
        ("entry-1", "entry-4"),
        "qwen3",
        cancellation_check=lambda: cancellation["requested"],
    )

    assert result.cancelled is True
    assert result.translated_entry_ids == ("entry-1",)
    assert llm_client.calls == 1
    assert repository.get_entry("project-1", "entry-4").translation is None
