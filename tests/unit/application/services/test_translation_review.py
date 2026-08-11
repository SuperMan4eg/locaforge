from collections.abc import Sequence

import pytest

from locaforge.application.errors import ModelUnavailableError
from locaforge.application.services.translation_review import TranslationReviewService
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.project import Project
from locaforge.domain.settings import ModelSettings


class Repository:
    def __init__(self, entry: TranslationEntry | None = None) -> None:
        self.entry = entry
        self.operations: list[tuple[object, ...]] = []

    def get_entry(self, _project_id: str, _entry_id: str) -> TranslationEntry:
        assert self.entry is not None
        return self.entry

    def get_entries(
        self, _project_id: str, entry_ids: Sequence[str]
    ) -> tuple[TranslationEntry, ...]:
        assert self.entry is not None
        return tuple(self.entry for _entry_id in entry_ids)

    def list_validation_issues(self, _project_id: str) -> tuple[()]:
        return ()

    def record_translation_operation(self, *args: object) -> None:
        self.operations.append(args)


class LlmClient:
    def review(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("Cancellation must happen before the model call")


def test_requires_configured_llm_backend() -> None:
    service = TranslationReviewService(None)

    with pytest.raises(ModelUnavailableError):
        service.review(  # type: ignore[arg-type]
            Repository(), Project("p", "Demo", "en", "ru"), (), ModelSettings()
        )


def test_cancellation_before_first_batch_records_no_changes() -> None:
    entry = TranslationEntry("entry-1", ("text",), "Hello", translation="Привет")
    repository = Repository(entry)
    service = TranslationReviewService(None)
    service.set_llm_client(LlmClient())  # type: ignore[arg-type]
    progress: list[tuple[int, int]] = []

    run = service.review(  # type: ignore[arg-type]
        repository,
        Project("p", "Demo", "en", "ru", entries=[entry]),
        (entry.id,),
        ModelSettings(),
        progress_callback=lambda completed, total: progress.append((completed, total)),
        cancellation_check=lambda: True,
    )

    assert run.result.cancelled is True
    assert run.result.reviewed_entries == 0
    assert run.project_changed is False
    assert progress == [(0, 1)]
    assert repository.operations == [
        ("p", (), {"entry-1": ()}, "Review translations")
    ]
