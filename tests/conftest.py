"""Shared pytest policy and fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


def _test_layer(path: Path) -> str:
    """Assign every test file to one architecture-aligned execution layer."""
    normalized = path.as_posix()
    if "/presentation/" in normalized:
        return "gui"
    if "/infrastructure/" in normalized:
        return "integration"
    if "/application/use_cases/" in normalized:
        return "integration"
    if path.name in {
        "test_multi_file_project_lifecycle.py",
        "test_project_workspace.py",
    }:
        return "integration"
    return "unit"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply one and only one execution-layer marker to each collected test."""
    for item in items:
        item.add_marker(_test_layer(Path(str(item.path))))


@pytest.fixture(scope="session")
def qt_application() -> Iterator[object]:
    """Keep a single QApplication alive across the GUI test session."""
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture(autouse=True)
def _keep_qt_application_alive(request: pytest.FixtureRequest) -> None:
    """Avoid repeatedly destroying and recreating QApplication in GUI tests."""
    if request.node.get_closest_marker("gui") is not None:
        request.getfixturevalue("qt_application")
