"""XML adapter for translating text content of leaf elements."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

from locaforge.application.ports.xml_format import XmlFieldMapping
from locaforge.domain.entry import TranslationEntry
from locaforge.domain.project import Project


class InvalidXmlError(ValueError):
    pass


class XmlFileFormat:
    """Keeps XML structure while exposing leaf text as translation entries."""

    def import_file(
        self,
        path: Path,
        source_language: str,
        target_language: str,
        field_mapping: XmlFieldMapping | None = None,
    ) -> Project:
        root, has_declaration = self._parse_path(path)
        entries = list(self._collect_entries(root, field_mapping or XmlFieldMapping()))
        return Project(
            id=str(uuid4()),
            name=path.stem,
            source_language=source_language,
            target_language=target_language,
            entries=entries,
            source_document={
                "format": "xml",
                "document": ElementTree.tostring(root, encoding="unicode"),
                "has_declaration": has_declaration,
            },
        )

    def inspect_attribute_names(self, path: Path) -> tuple[str, ...]:
        root, _ = self._parse_path(path)
        return tuple(
            sorted(
                {
                    name
                    for _, element in self._walk(root)
                    for name, value in element.attrib.items()
                    if self._is_translatable(value)
                }
            )
        )

    def export_file(self, project: Project, destination: Path) -> None:
        document = project.source_document
        if not isinstance(document, dict) or document.get("format") != "xml":
            raise InvalidXmlError("Project has no XML source document")
        source = document.get("document")
        if not isinstance(source, str):
            raise InvalidXmlError("XML source document is invalid")
        root = self._parse_text(source)
        for entry in project.entries:
            if entry.translation is None:
                continue
            if len(entry.key_path) >= 3 and entry.key_path[-2] == "attributes":
                element = self._element_at_path(root, entry.key_path[:-2])
                element.set(str(entry.key_path[-1]), entry.translation)
            else:
                element = self._element_at_path(root, entry.key_path)
                element.text = entry.translation
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            ElementTree.ElementTree(root).write(
                destination,
                encoding="utf-8",
                xml_declaration=bool(document.get("has_declaration")),
            )
        except OSError as error:
            raise InvalidXmlError(f"Cannot export XML file to {destination}") from error

    def _collect_entries(
        self, root: ElementTree.Element, field_mapping: XmlFieldMapping
    ) -> Iterator[TranslationEntry]:
        for path, element in self._walk(root):
            if not len(element) and self._is_translatable(element.text):
                yield TranslationEntry(
                    id=str(uuid4()),
                    key_path=("elements", *path),
                    source=element.text or "",
                    context=self._display_tag(element.tag),
                    key=self._entry_key(element),
                )
            for attribute_name in field_mapping.attribute_names:
                value = element.get(attribute_name)
                if not self._is_translatable(value):
                    continue
                yield TranslationEntry(
                    id=str(uuid4()),
                    key_path=("elements", *path, "attributes", attribute_name),
                    source=value or "",
                    context=f"{self._display_tag(element.tag)} @{attribute_name}",
                    key=f"{self._entry_key(element)}@{attribute_name}",
                )

    @staticmethod
    def _walk(
        root: ElementTree.Element,
    ) -> Iterator[tuple[tuple[int, ...], ElementTree.Element]]:
        stack: list[tuple[tuple[int, ...], ElementTree.Element]] = [((), root)]
        while stack:
            path, element = stack.pop()
            yield path, element
            stack.extend(
                (path + (index,), child)
                for index, child in reversed(tuple(enumerate(element)))
                if isinstance(child.tag, str)
            )

    def _element_at_path(
        self, root: ElementTree.Element, key_path: tuple[str | int, ...]
    ) -> ElementTree.Element:
        if not key_path or key_path[0] != "elements":
            raise InvalidXmlError("Entry path does not match XML source document")
        element = root
        try:
            for index in key_path[1:]:
                element = element[int(index)]
        except (IndexError, TypeError, ValueError) as error:
            raise InvalidXmlError("Entry path does not match XML source document") from error
        return element

    def _parse_path(self, path: Path) -> tuple[ElementTree.Element, bool]:
        try:
            raw = path.read_bytes()
            root = ElementTree.fromstring(raw, parser=self._parser())
        except (OSError, ElementTree.ParseError) as error:
            raise InvalidXmlError(f"Cannot import XML file {path.name!r}") from error
        return root, raw.lstrip().startswith(b"<?xml")

    def _parse_text(self, text: str) -> ElementTree.Element:
        try:
            return ElementTree.fromstring(text, parser=self._parser())
        except ElementTree.ParseError as error:
            raise InvalidXmlError("XML source document is invalid") from error

    @staticmethod
    def _parser() -> ElementTree.XMLParser:
        return ElementTree.XMLParser(target=ElementTree.TreeBuilder(insert_comments=True))

    @staticmethod
    def _is_translatable(text: str | None) -> bool:
        return text is not None and bool(text.strip()) and any(
            character.isalpha() for character in text
        )

    @staticmethod
    def _display_tag(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    def _entry_key(self, element: ElementTree.Element) -> str:
        identifier = next(
            (
                value
                for name, value in element.attrib.items()
                if name.casefold() in {"id", "key", "name"}
            ),
            None,
        )
        tag = self._display_tag(element.tag)
        return f"{tag}:{identifier}" if identifier else tag
