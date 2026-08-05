import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from locaforge.application.dto.validation import ProjectValidationResult
from locaforge.presentation.validation_worker import ValidationWorker


def test_worker_delivers_project_validation_result() -> None:
    application = QApplication.instance() or QApplication([])
    expected = ProjectValidationResult(8, 2)
    received: list[object] = []
    worker = ValidationWorker(lambda: expected)
    worker.succeeded.connect(received.append)

    worker.start()
    worker.wait()
    application.processEvents()

    assert received == [expected]
