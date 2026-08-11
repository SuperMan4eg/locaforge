import pytest

from locaforge.application.errors import ModelUnavailableError
from locaforge.application.services.model_configuration import ModelConfigurationService
from locaforge.domain.project import Project
from locaforge.domain.settings import ModelSettings


class LlmClient:
    def __init__(self) -> None:
        self.pulled: list[str] = []

    def list_models(self) -> tuple[str, ...]:
        return ("model-a", "model-b")

    def health_check(self) -> bool:
        return True

    def pull_model(self, model: str) -> None:
        self.pulled.append(model)


class Repository:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.saved: list[Project] = []

    def get(self, _project_id: str) -> Project:
        return self.project

    def save(self, project: Project) -> None:
        self.saved.append(project)


def test_resolves_global_settings_until_project_override_is_enabled() -> None:
    service = ModelConfigurationService(None)
    global_settings = ModelSettings(model="global-model", batch_size=3)
    project = Project("p", "Demo", "en", "ru")
    repository = Repository(project)
    service.set_global_settings(global_settings)

    assert service.resolve(project) == global_settings
    assert service.source(project) == "global"

    overridden = service.set_project_override(repository, project, True)  # type: ignore[arg-type]
    service.set_global_settings(ModelSettings(model="new-global"))

    assert service.resolve(overridden) == global_settings
    assert service.source(overridden) == "project"
    assert repository.saved == [overridden]


def test_exposes_and_replaces_llm_backend() -> None:
    service = ModelConfigurationService(None)

    assert service.health_check() is False
    with pytest.raises(ModelUnavailableError):
        service.list_models()
    with pytest.raises(ModelUnavailableError):
        service.pull_model("model-a")

    client = LlmClient()
    service.set_llm_client(client)  # type: ignore[arg-type]

    assert service.health_check() is True
    assert service.list_models() == ("model-a", "model-b")
    service.pull_model("model-b")
    assert client.pulled == ["model-b"]
