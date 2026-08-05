import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from locaforge.domain.settings import ModelSettings
from locaforge.presentation.ollama_settings_dialog import OllamaSettingsDialog


def test_dialog_returns_current_project_model_settings() -> None:
    application = QApplication.instance() or QApplication([])
    settings = ModelSettings(
        "qwen3:8b",
        75.0,
        16,
        "Keep dialogue concise.",
        "Reject changes in meaning.",
    )
    dialog = OllamaSettingsDialog(
        settings, ("gemma3:12b", "qwen3:8b"), "Connected"
    )

    assert application is not None
    assert dialog.model_settings() == settings
    dialog.close()
