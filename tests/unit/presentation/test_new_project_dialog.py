import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from locaforge.domain.project import Project
from locaforge.domain.project_profile import ProjectProfile
from locaforge.domain.settings import ModelSettings
from locaforge.presentation.new_project_dialog import NewProjectDialog


def test_new_project_dialog_returns_profile() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = NewProjectDialog()
    dialog.name.setText("Nebula")
    dialog.description.setPlainText(" Space exploration game ")
    dialog.project_type.setCurrentText("Game")
    dialog.tone.setText("Friendly")

    name, source_language, target_language, profile = dialog.project_values()

    assert application is not None
    assert (name, source_language, target_language) == ("Nebula", "en", "ru")
    assert profile.description == "Space exploration game"
    assert profile.project_type == "Game"
    assert profile.tone == "Friendly"


def test_new_project_dialog_applies_generated_profile() -> None:
    application = QApplication.instance() or QApplication([])
    requested_names: list[str] = []

    def generate(name: str, *, use_online_lookup: bool = False) -> ProjectProfile:
        assert use_online_lookup is False
        requested_names.append(name)
        return ProjectProfile(
            description="A generated description",
            project_type="Game",
            domain="Science fiction",
            target_audience="Adults",
            tone="Cinematic",
            platform="PC",
            translation_instructions="Keep faction names consistent.",
        )

    dialog = NewProjectDialog(profile_generator=generate)
    dialog.name.setText("Nebula")
    dialog.generate_profile.click()
    for _ in range(100):
        application.processEvents()
        if dialog.generate_profile.isEnabled():
            break
        QTest.qWait(10)

    assert application is not None
    assert requested_names == ["Nebula"]
    assert dialog.description.toPlainText() == "A generated description"
    assert dialog.project_type.currentText() == "Game"
    assert dialog.domain.text() == "Science fiction"
    assert dialog.instructions.toPlainText() == "Keep faction names consistent."


def test_project_override_exposes_and_returns_model_settings() -> None:
    application = QApplication.instance() or QApplication([])
    project = Project("project", "Project", "en", "ru")
    global_settings = ModelSettings(model="global", timeout_seconds=10.5)
    dialog = NewProjectDialog(project=project, global_model_settings=global_settings)

    dialog.model_settings_override.setChecked(True)
    dialog.translation_model.setCurrentText("project-model")
    dialog.model_timeout.setValue(42.5)

    assert application is not None
    assert not dialog.model_settings_panel.isHidden()
    assert dialog.project_model_settings().model == "project-model"
    assert dialog.project_model_settings().timeout_seconds == 42.5
