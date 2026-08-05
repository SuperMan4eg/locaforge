import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from locaforge.presentation.autosave_controller import AutosaveController


def test_autosave_can_be_scheduled_and_flushed() -> None:
    application = QApplication.instance() or QApplication([])
    calls: list[str] = []
    controller = AutosaveController(lambda: calls.append("saved"), delay_ms=1000)

    controller.schedule()
    assert controller.is_pending is True
    controller.flush()

    assert application is not None
    assert controller.is_pending is False
    assert calls == ["saved"]


def test_autosave_reports_save_failure() -> None:
    application = QApplication.instance() or QApplication([])
    errors: list[str] = []

    def fail() -> None:
        raise OSError("disk unavailable")

    controller = AutosaveController(fail)
    controller.failed.connect(errors.append)
    controller.flush()

    assert application is not None
    assert errors == ["disk unavailable"]
