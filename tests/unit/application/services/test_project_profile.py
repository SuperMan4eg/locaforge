from pathlib import Path

import pytest

from locaforge.application.dto.project_description import (
    ProjectDescriptionRequest,
    ProjectDescriptionResponse,
)
from locaforge.application.errors import ModelUnavailableError
from locaforge.application.project_session import ProjectSession
from locaforge.application.services.project_profile import ProjectProfileService
from locaforge.domain.project import Project
from locaforge.domain.project_profile import ProjectProfile
from locaforge.domain.settings import ModelSettings


class LlmClient:
    def __init__(self) -> None:
        self.requests: list[ProjectDescriptionRequest] = []

    def describe_project(
        self, request: ProjectDescriptionRequest
    ) -> ProjectDescriptionResponse:
        self.requests.append(request)
        return ProjectDescriptionResponse(ProjectProfile(description="Generated"))


class Lookup:
    def __init__(self) -> None:
        self.names: list[str] = []

    def lookup(self, project_name: str) -> str:
        self.names.append(project_name)
        return "Research context"


class Repository:
    def __init__(self) -> None:
        self.saved: list[Project] = []

    def save(self, project: Project) -> None:
        self.saved.append(project)


def test_generates_profile_with_normalized_name_and_online_context() -> None:
    llm = LlmClient()
    lookup = Lookup()
    service = ProjectProfileService(llm, lookup)  # type: ignore[arg-type]

    profile = service.generate(
        "  Nebula  ",
        ModelSettings(model="model-a", timeout_seconds=42, keep_alive_seconds=900),
        use_online_lookup=True,
    )

    assert profile.description == "Generated"
    assert lookup.names == ["Nebula"]
    request = llm.requests[0]
    assert request.name == "Nebula"
    assert request.research_context == "Research context"
    assert request.keep_alive_seconds == 900


def test_generation_requires_backend_name_and_configured_lookup() -> None:
    settings = ModelSettings()
    with pytest.raises(ModelUnavailableError, match="backend"):
        ProjectProfileService(None, None).generate("Demo", settings)
    service = ProjectProfileService(LlmClient(), None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="project name"):
        service.generate("  ", settings)
    with pytest.raises(ModelUnavailableError, match="lookup"):
        service.generate("Demo", settings, use_online_lookup=True)


def test_updates_project_and_session_metadata(tmp_path: Path) -> None:
    project = Project("p", "Old", "en", "de")
    session = ProjectSession(tmp_path, tmp_path / "project.db", {})
    repository = Repository()
    profile = ProjectProfile(description="Updated")

    ProjectProfileService.update(  # type: ignore[arg-type]
        repository, session, project, " New ", " en-US ", " uk ", profile
    )

    assert (project.name, project.source_language, project.target_language) == (
        "New",
        "en-US",
        "uk",
    )
    assert project.profile == profile
    assert project.dirty is True
    assert session.metadata == {
        "project_name": "New",
        "source_language": "en-US",
        "target_language": "uk",
    }
    assert repository.saved == [project]


@pytest.mark.parametrize(
    ("name", "source", "target"),
    [("", "en", "ru"), ("Demo", "", "ru"), ("Demo", "en", " EN ")],
)
def test_rejects_invalid_profile_identity(
    tmp_path: Path, name: str, source: str, target: str
) -> None:
    with pytest.raises(ValueError):
        ProjectProfileService.update(  # type: ignore[arg-type]
            Repository(),
            ProjectSession(tmp_path, tmp_path / "project.db", {}),
            Project("p", "Demo", "en", "ru"),
            name,
            source,
            target,
            ProjectProfile(),
        )
