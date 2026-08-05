"""Field-mapping dialogs for structured localization imports."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QInputDialog, QMessageBox, QWidget

from locaforge.application.ports.csv_format import CsvFieldMapping
from locaforge.application.ports.json_format import JsonFieldMapping
from locaforge.application.ports.xml_format import XmlFieldMapping
from locaforge.application.project_workspace import ProjectWorkspace
from locaforge.presentation.json_import_profiles import (
    JsonImportProfile,
    JsonImportProfileStore,
)


class ImportMappingController:
    """Collects optional JSON, CSV, and XML field mappings from the user."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        json_profiles: JsonImportProfileStore,
        parent: QWidget,
    ) -> None:
        self._workspace = workspace
        self._json_profiles = json_profiles
        self._parent = parent

    def ask_json(self, path: Path) -> JsonFieldMapping | None:
        fields = self._workspace.inspect_json_fields(path)
        if not fields:
            return None
        available_profiles = tuple(
            profile
            for profile in self._json_profiles.list_profiles()
            if profile.mapping.source_field in fields
            and profile.mapping.target_field in fields
            and (profile.mapping.key_field is None or profile.mapping.key_field in fields)
        )
        if available_profiles:
            profile_names = (
                "<configure fields>",
                *(profile.name for profile in available_profiles),
            )
            selected_name, accepted = QInputDialog.getItem(
                self._parent,
                "JSON import profile",
                "Use import profile:",
                profile_names,
                0,
                False,
            )
            if not accepted:
                return None
            if selected_name != "<configure fields>":
                return next(
                    profile.mapping
                    for profile in available_profiles
                    if profile.name == selected_name
                )
        if QMessageBox.question(
            self._parent,
            "JSON import fields",
            "Detected object fields:\n"
            f"{', '.join(fields)}\n\nSelect only localization fields?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        ) != QMessageBox.StandardButton.Yes:
            return None
        source_field, accepted = QInputDialog.getItem(
            self._parent, "JSON import fields", "Source text field:", fields, 0, False
        )
        if not accepted:
            return None
        target_field, accepted = QInputDialog.getItem(
            self._parent,
            "JSON import fields",
            "Translation field:",
            fields,
            0,
            False,
        )
        if not accepted or target_field == source_field:
            return None
        key_options = ("<generated path>", *fields)
        key_field, accepted = QInputDialog.getItem(
            self._parent, "JSON import fields", "Key field:", key_options, 0, False
        )
        if not accepted:
            return None
        mapping = JsonFieldMapping(
            source_field,
            target_field,
            None if key_field == "<generated path>" else key_field,
            QMessageBox.question(
                self._parent,
                "Existing translations",
                "Import existing target-field values as translations needing review?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            == QMessageBox.StandardButton.Yes,
        )
        if QMessageBox.question(
            self._parent,
            "JSON import profile",
            "Save this field mapping as a reusable profile?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            profile_name, accepted = QInputDialog.getText(
                self._parent, "JSON import profile", "Profile name:"
            )
            if accepted and profile_name.strip():
                self._json_profiles.save(JsonImportProfile(profile_name.strip(), mapping))
        return mapping

    def ask_csv(self, path: Path) -> CsvFieldMapping | None:
        fields = self._workspace.inspect_csv_fields(path)
        source_field, accepted = QInputDialog.getItem(
            self._parent, "CSV import fields", "Source text field:", fields, 0, False
        )
        if not accepted:
            return None
        target_field, accepted = QInputDialog.getItem(
            self._parent,
            "CSV import fields",
            "Translation field:",
            fields,
            0,
            False,
        )
        if not accepted or target_field == source_field:
            return None
        key_options = ("<generated row>", *fields)
        key_field, accepted = QInputDialog.getItem(
            self._parent, "CSV import fields", "Key field:", key_options, 0, False
        )
        if not accepted:
            return None
        import_existing = QMessageBox.question(
            self._parent,
            "Existing translations",
            "Import existing target-column values as translations needing review?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        ) == QMessageBox.StandardButton.Yes
        return CsvFieldMapping(
            source_field,
            target_field,
            None if key_field == "<generated row>" else key_field,
            import_existing,
        )

    def ask_xml(self, path: Path) -> XmlFieldMapping | None:
        attribute_names = self._workspace.inspect_xml_attribute_names(path)
        if not attribute_names:
            return None
        if QMessageBox.question(
            self._parent,
            "XML attributes",
            "Also import text from selected XML attributes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return None
        selected_names, accepted = QInputDialog.getText(
            self._parent,
            "XML attributes",
            "Attribute names (comma-separated):\n"
            f"Available: {', '.join(attribute_names)}",
        )
        if not accepted or not selected_names.strip():
            return None
        selected = tuple(
            name.strip() for name in selected_names.split(",") if name.strip()
        )
        unknown_names = sorted(set(selected).difference(attribute_names))
        if unknown_names:
            QMessageBox.warning(
                self._parent,
                "XML attributes",
                f"Unknown attribute names: {', '.join(unknown_names)}",
            )
            return None
        return XmlFieldMapping(selected)
