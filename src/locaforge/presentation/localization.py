"""JSON based interface localization with a safe English fallback."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QWidget,
)

_PLACEHOLDER = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)[^}]*\}(?!\})")
_REQUIRED_METADATA = {"locale", "name", "fallback", "format_version"}
_installed_manager: LocalizationManager | None = None


def tr(key: str, english: str, /, **parameters: object) -> str:
    """Translate through the active application manager, with an English fallback."""

    if _installed_manager is None:
        return english.format(**parameters)
    translated = _installed_manager.translate(key, **parameters)
    return english.format(**parameters) if translated == "Translation unavailable" else translated


def tr_source(source: str) -> str:
    """Translate a catalogued source string through the active manager."""

    return source if _installed_manager is None else _installed_manager.translate_source(source)


@dataclass(frozen=True, slots=True)
class PackageDiagnostic:
    path: Path | None
    level: str
    message: str


@dataclass(frozen=True, slots=True)
class LanguagePackage:
    locale: str
    name: str
    fallback: str
    messages: Mapping[str, str]


class LocalizationManager(QObject):
    """Loads bundled and user packages; English is always present in memory."""

    languageChanged = Signal(str)

    def __init__(self, user_directory: Path, locale: str = "en") -> None:
        super().__init__()
        self.user_directory = user_directory
        self._packages: dict[str, LanguagePackage] = {}
        self.diagnostics: list[PackageDiagnostic] = []
        self.locale = "en"
        self._source_to_key: dict[str, str] = {}
        self._localized_to_source: dict[str, str] = {}
        self._application: QApplication | None = None
        self.reload()
        self.set_locale(locale)

    @property
    def available_languages(self) -> tuple[LanguagePackage, ...]:
        return tuple(sorted(self._packages.values(), key=lambda package: package.name.casefold()))

    def set_locale(self, locale: str) -> None:
        """Select an installed locale and notify every open UI component."""

        resolved = self._resolve_locale(locale)
        if resolved == self.locale:
            return
        self.locale = resolved
        self.languageChanged.emit(resolved)

    def resolve_locale(self, locale: str) -> str:
        """Resolve an OS or regional locale to one of the installed packages."""

        return self._resolve_locale(locale)

    def _resolve_locale(self, locale: str) -> str:
        normalized = locale.strip().replace("_", "-")
        if normalized in self._packages:
            return normalized
        language = normalized.split("-", 1)[0].lower()
        for package_locale in self._packages:
            if package_locale.split("-", 1)[0].lower() == language:
                return package_locale
        return "en"

    def translate(self, key: str, /, **parameters: object) -> str:
        english = self._packages["en"].messages
        message = self._packages.get(self.locale, self._packages["en"]).messages.get(
            key, english.get(key, "Translation unavailable")
        )
        expected = set(_PLACEHOLDER.findall(message))
        if expected != set(parameters):
            missing = ", ".join(sorted(expected - set(parameters)))
            extra = ", ".join(sorted(set(parameters) - expected))
            details = ", ".join(
                part
                for part in (missing and f"missing: {missing}", extra and f"unexpected: {extra}")
                if part
            )
            self.diagnostics.append(
                PackageDiagnostic(None, "error", f"{key}: parameter mismatch ({details})")
            )
            return message
        try:
            return message.format(**parameters)
        except (KeyError, ValueError):
            return message

    def translate_source(self, source: str) -> str:
        """Translate a visible English source string when it is catalogued."""

        canonical_source = self._localized_to_source.get(source, source)
        key = self._source_to_key.get(canonical_source)
        return canonical_source if key is None else self.translate(key)

    def install(self, application: QApplication) -> None:
        """Install automatic localization for every widget shown by the application."""

        global _installed_manager
        if self._application is application:
            return
        if _installed_manager is not None and _installed_manager is not self:
            if _installed_manager._application is not None:
                _installed_manager._application.removeEventFilter(_installed_manager)
            _installed_manager._application = None
        if self._application is not None:
            self._application.removeEventFilter(self)
        self._application = application
        _installed_manager = self
        application.installEventFilter(self)
        self.languageChanged.connect(self._retranslate_open_windows)

    @staticmethod
    def uninstall_active(application: QApplication) -> None:
        """Remove an earlier automatic localizer from an application."""

        global _installed_manager
        if _installed_manager is None:
            return
        application.removeEventFilter(_installed_manager)
        _installed_manager._application = None
        _installed_manager = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Show and isinstance(watched, QWidget):
            self.localize_widget(watched)
        return super().eventFilter(watched, event)

    def localize_widget(self, root: QWidget) -> None:
        """Translate a widget and all of its QObject children in place."""

        objects: tuple[QObject, ...] = (root, *root.findChildren(QObject))
        for obj in objects:
            self._localize_object(obj)

    def _retranslate_open_windows(self, _locale: str) -> None:
        if self._application is None:
            return
        for widget in self._application.topLevelWidgets():
            self.localize_widget(widget)

    def _localize_object(self, obj: QObject) -> None:
        if isinstance(obj, QAction):
            obj.setText(self.translate_source(obj.text()))
            obj.setToolTip(self.translate_source(obj.toolTip()))
            obj.setStatusTip(self.translate_source(obj.statusTip()))
        if isinstance(obj, QWidget):
            obj.setWindowTitle(self.translate_source(obj.windowTitle()))
            obj.setToolTip(self.translate_source(obj.toolTip()))
        if isinstance(obj, QAbstractButton):
            obj.setText(self.translate_source(obj.text()))
        if isinstance(obj, QLabel):
            obj.setText(self.translate_source(obj.text()))
        if isinstance(obj, QGroupBox):
            obj.setTitle(self.translate_source(obj.title()))
        if isinstance(obj, QLineEdit | QPlainTextEdit | QTextEdit):
            obj.setPlaceholderText(self.translate_source(obj.placeholderText()))
        if isinstance(obj, QComboBox):
            for index in range(obj.count()):
                obj.setItemText(index, self.translate_source(obj.itemText(index)))
        if isinstance(obj, QTabWidget):
            for index in range(obj.count()):
                obj.setTabText(index, self.translate_source(obj.tabText(index)))
        if isinstance(obj, QTreeWidget):
            tree_header = obj.headerItem()
            for column in range(obj.columnCount()):
                tree_header.setText(
                    column, self.translate_source(tree_header.text(column))
                )
        if isinstance(obj, QTableWidget):
            for column in range(obj.columnCount()):
                table_header = obj.horizontalHeaderItem(column)
                if table_header is not None:
                    table_header.setText(self.translate_source(table_header.text()))

    def reload(self) -> list[PackageDiagnostic]:
        self.diagnostics = []
        self._packages = {}
        bundled = files("locaforge.resources.locales")
        for resource in bundled.iterdir():
            if resource.name.endswith(".json") and resource.name != "template.json":
                self._load_mapping(
                    resource.name, json.loads(resource.read_text(encoding="utf-8")), None
                )
        if "en" not in self._packages:
            raise RuntimeError("The bundled English localization package is required.")
        self.user_directory.mkdir(parents=True, exist_ok=True)
        template = self.user_directory / "template.json"
        template.write_text(
            json.dumps(
                {
                    "metadata": {
                        "locale": "xx",
                        "name": "My language",
                        "fallback": "en",
                        "format_version": 1,
                    },
                    "messages": self._packages["en"].messages,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        for path in sorted(self.user_directory.glob("*.json")):
            if path.name == "template.json":
                continue
            self._load_file(path)
        self._rebuild_source_indexes()
        self.set_locale(self.locale)
        return self.diagnostics

    def _rebuild_source_indexes(self) -> None:
        english = self._packages["en"].messages
        counts: dict[str, int] = {}
        for source in english.values():
            counts[source] = counts.get(source, 0) + 1
        self._source_to_key = {
            source: key for key, source in english.items() if counts[source] == 1
        }
        self._localized_to_source = {}
        for key, source in english.items():
            if counts[source] != 1:
                continue
            self._localized_to_source[source] = source
            for package in self._packages.values():
                translated = package.messages.get(key)
                if translated is not None:
                    self._localized_to_source[translated] = source

    def validate_user_packages(self) -> list[PackageDiagnostic]:
        previous_locale = self.locale
        self.reload()
        self.set_locale(previous_locale)
        return self.diagnostics

    def _load_file(self, path: Path) -> None:
        try:
            value: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            self.diagnostics.append(PackageDiagnostic(path, "error", f"Invalid JSON: {error}"))
            return
        self._load_mapping(path.name, value, path)

    def _load_mapping(self, source: str, value: Any, path: Path | None) -> None:
        if not isinstance(value, dict):
            self.diagnostics.append(
                PackageDiagnostic(path, "error", f"{source}: root must be an object")
            )
            return
        metadata, messages = value.get("metadata"), value.get("messages")
        if not isinstance(metadata, dict) or not isinstance(messages, dict):
            self.diagnostics.append(
                PackageDiagnostic(
                    path, "error", f"{source}: metadata and messages are required objects"
                )
            )
            return
        missing_metadata = _REQUIRED_METADATA - set(metadata)
        if missing_metadata or metadata.get("format_version") != 1:
            self.diagnostics.append(
                PackageDiagnostic(
                    path,
                    "error",
                    f"{source}: invalid metadata "
                    f"({', '.join(sorted(missing_metadata)) or 'format_version'})",
                )
            )
            return
        locale, name, fallback = (
            metadata.get("locale"),
            metadata.get("name"),
            metadata.get("fallback"),
        )
        if not (
            isinstance(locale, str)
            and locale.strip()
            and isinstance(name, str)
            and name.strip()
            and isinstance(fallback, str)
            and fallback.strip()
        ):
            self.diagnostics.append(
                PackageDiagnostic(
                    path, "error", f"{source}: locale, name, and fallback must be non-empty strings"
                )
            )
            return
        if fallback != "en":
            self.diagnostics.append(
                PackageDiagnostic(path, "error", f"{source}: fallback must be 'en'")
            )
            return
        if path is not None and locale == "en":
            self.diagnostics.append(
                PackageDiagnostic(
                    path, "error", f"{source}: the built-in English package cannot be replaced"
                )
            )
            return
        if any(
            not isinstance(key, str) or not isinstance(text, str) or not text
            for key, text in messages.items()
        ):
            self.diagnostics.append(
                PackageDiagnostic(
                    path, "error", f"{source}: message keys and values must be non-empty strings"
                )
            )
            return
        if locale != "en":
            english = self._packages.get("en")
            if english is not None:
                unknown = set(messages) - set(english.messages)
                absent = set(english.messages) - set(messages)
                if unknown:
                    self.diagnostics.append(
                        PackageDiagnostic(
                            path, "error", f"{source}: unknown keys: {', '.join(sorted(unknown))}"
                        )
                    )
                if absent:
                    self.diagnostics.append(
                        PackageDiagnostic(
                            path,
                            "warning",
                            f"{source}: missing strings: {', '.join(sorted(absent))}",
                        )
                    )
                for key in set(messages) & set(english.messages):
                    if set(_PLACEHOLDER.findall(messages[key])) != set(
                        _PLACEHOLDER.findall(english.messages[key])
                    ):
                        self.diagnostics.append(
                            PackageDiagnostic(
                                path, "error", f"{source}: {key} has different parameters"
                            )
                        )
                if unknown:
                    return
        self._packages[locale] = LanguagePackage(locale, name, fallback, dict(messages))
