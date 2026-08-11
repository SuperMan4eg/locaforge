import pytest

from locaforge.application.errors import ModelUnavailableError
from locaforge.application.services.batch_translation import BatchTranslationService
from locaforge.domain.project import Project
from locaforge.domain.settings import ModelSettings


class Repository:
    def __init__(self) -> None:
        self.operations: list[tuple[object, ...]] = []

    def list_validation_issues(self, _project_id: str) -> tuple[()]:
        return ()

    def record_translation_operation(self, *args: object) -> None:
        self.operations.append(args)


class LlmClient:
    def translate(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("An empty selection must not call the model")


def test_requires_configured_llm_backend() -> None:
    service = BatchTranslationService(None, None, None)

    with pytest.raises(ModelUnavailableError):
        service.translate(Repository(), Project("p", "Demo", "en", "ru"), (), ModelSettings())  # type: ignore[arg-type]


def test_empty_selection_reports_progress_and_records_empty_operation() -> None:
    repository = Repository()
    service = BatchTranslationService(None, None, None)
    service.set_llm_client(LlmClient())  # type: ignore[arg-type]
    progress: list[tuple[int, int]] = []

    result = service.translate(  # type: ignore[arg-type]
        repository,
        Project("p", "Demo", "en", "ru"),
        (),
        ModelSettings(),
        progress_callback=lambda completed, total: progress.append((completed, total)),
    )

    assert result.translated_entry_ids == ()
    assert result.cancelled is False
    assert progress == [(0, 0)]
    assert repository.operations == [("p", (), {}, "Translate entries")]
