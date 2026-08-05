import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from locaforge.presentation.model_pull_worker import ModelPullWorker


def test_model_pull_worker_reports_installed_model() -> None:
    application = QApplication.instance() or QApplication([])
    installed: list[str] = []
    worker = ModelPullWorker("qwen3:8b", lambda: None)
    worker.succeeded.connect(installed.append)

    worker.start()
    worker.wait()
    application.processEvents()

    assert installed == ["qwen3:8b"]
