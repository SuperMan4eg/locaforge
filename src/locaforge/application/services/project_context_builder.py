"""Build bounded, human-readable project context for language models."""

from __future__ import annotations

from locaforge.domain.project import Project


class ProjectContextBuilder:
    def __init__(self, max_characters: int = 3000) -> None:
        if max_characters < 200:
            raise ValueError("Project context limit must be at least 200 characters")
        self._max_characters = max_characters

    def build(self, project: Project) -> str:
        profile = project.profile
        values = (
            ("Project", project.name),
            ("Type", profile.project_type),
            ("Domain or genre", profile.domain),
            ("Platform", profile.platform),
            ("Target audience", profile.target_audience),
            ("Tone", profile.tone),
            ("Translation instructions", profile.translation_instructions),
            ("Description", profile.description),
        )
        lines = [f"{label}: {value.strip()}" for label, value in values if value.strip()]
        if not lines:
            return ""
        context = "Project context:\n" + "\n".join(lines)
        if len(context) <= self._max_characters:
            return context
        suffix = "\n[Project context truncated]"
        return context[: self._max_characters - len(suffix)].rstrip() + suffix

    def combine_with_prompt(self, project: Project, prompt: str) -> str:
        sections = tuple(
            section for section in (prompt.strip(), self.build(project)) if section
        )
        return "\n\n".join(sections)
