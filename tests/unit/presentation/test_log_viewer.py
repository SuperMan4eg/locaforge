from __future__ import annotations

import logging

from locaforge.presentation.log_viewer import LogViewerController


def test_log_viewer_forwards_formatted_messages() -> None:
    logger = logging.getLogger("locaforge.tests.log_viewer")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    controller = LogViewerController(logger.name)
    messages: list[str] = []
    controller.message_logged.connect(messages.append)

    controller.attach()
    logger.info("Imported project")
    controller.detach()

    assert len(messages) == 1
    assert messages[0].endswith("INFO: Imported project")


def test_log_viewer_stops_receiving_messages_after_detach() -> None:
    logger = logging.getLogger("locaforge.tests.log_viewer.detach")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    controller = LogViewerController(logger.name)
    messages: list[str] = []
    controller.message_logged.connect(messages.append)

    controller.attach()
    logger.info("Visible")
    controller.detach()
    logger.info("Hidden")

    assert len(messages) == 1
