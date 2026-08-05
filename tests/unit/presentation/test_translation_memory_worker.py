import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from locaforge.domain.translation_memory import TranslationMemoryMatch, TranslationMemoryRecord
from locaforge.presentation.translation_memory_worker import TranslationMemoryWorker


def test_worker_delivers_translation_memory_matches() -> None:
    application = QApplication.instance() or QApplication([])
    received: list[tuple[int, object]] = []
    record = TranslationMemoryRecord("en", "ru", "Save", "Сохранить")
    matches = (TranslationMemoryMatch(record, 1.0),)
    worker = TranslationMemoryWorker(3, lambda: matches)
    worker.succeeded.connect(lambda request_id, matches: received.append((request_id, matches)))

    worker.start()
    worker.wait()
    application.processEvents()

    assert received == [(3, matches)]
