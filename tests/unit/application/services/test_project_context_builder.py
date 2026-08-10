from locaforge.application.services.project_context_builder import ProjectContextBuilder
from locaforge.domain.project import Project
from locaforge.domain.project_profile import ProjectProfile


def test_builds_context_from_project_profile() -> None:
    project = Project(
        "project-1",
        "Nebula",
        "en",
        "ru",
        profile=ProjectProfile(
            description="A space exploration game",
            project_type="Game",
            target_audience="Teenagers",
            tone="Friendly",
            translation_instructions="Keep faction names in English.",
        ),
    )

    context = ProjectContextBuilder().build(project)

    assert "Project: Nebula" in context
    assert "Type: Game" in context
    assert "Target audience: Teenagers" in context
    assert "Tone: Friendly" in context
    assert "Keep faction names in English." in context


def test_context_is_bounded_and_marks_truncation() -> None:
    project = Project(
        "project-1",
        "Nebula",
        "en",
        "ru",
        profile=ProjectProfile(description="x" * 1000),
    )

    context = ProjectContextBuilder(200).build(project)

    assert len(context) <= 200
    assert context.endswith("[Project context truncated]")


def test_user_prompt_precedes_generated_context() -> None:
    project = Project("project-1", "Nebula", "en", "ru")

    combined = ProjectContextBuilder().combine_with_prompt(project, "Be concise.")

    assert combined.startswith("Be concise.\n\nProject context:")
