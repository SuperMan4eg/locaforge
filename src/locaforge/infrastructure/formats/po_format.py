"""GNU gettext PO adapter with semantic round-trip preservation."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import cast
from uuid import uuid4

from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project


class InvalidPoError(ValueError):
    pass


type PoBlock = dict[str, object]


class PoFileFormat:
    _DIRECTIVE = re.compile(
        r"^(msgctxt|msgid_plural|msgid|msgstr(?:\[(\d+)\])?)\s+(.*)$"
    )

    def import_file(
        self, path: Path, source_language: str, target_language: str
    ) -> Project:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as error:
            raise InvalidPoError(f"Cannot import PO file {path.name!r}") from error
        blocks = [
            self._parse_block(block)
            for block in re.split(r"\r?\n\s*\r?\n", text)
            if block.strip()
        ]
        entries: list[TranslationEntry] = []
        for block_index, block in enumerate(blocks):
            msgid = block.get("msgid")
            if not isinstance(msgid, str) or not msgid:
                continue
            translations = block.get("msgstr")
            if not isinstance(translations, dict):
                continue
            plural_source = block.get("msgid_plural")
            context = block.get("msgctxt")
            for plural_index, existing in sorted(
                translations.items(), key=lambda item: int(item[0])
            ):
                source = (
                    plural_source
                    if plural_index != "0" and isinstance(plural_source, str)
                    else msgid
                )
                translation = existing if isinstance(existing, str) and existing else None
                entries.append(
                    TranslationEntry(
                        id=str(uuid4()),
                        key_path=("blocks", block_index, "msgstr", plural_index),
                        source=source,
                        translation=translation,
                        status=(
                            EntryStatus.NEEDS_REVIEW
                            if translation
                            else EntryStatus.UNTRANSLATED
                        ),
                        context=context if isinstance(context, str) else None,
                        key=context if isinstance(context, str) and context else msgid,
                    )
                )
        return Project(
            id=str(uuid4()),
            name=path.stem,
            source_language=source_language,
            target_language=target_language,
            entries=entries,
            source_document={"format": "po", "blocks": blocks},
        )

    def export_file(self, project: Project, destination: Path) -> None:
        document = project.source_document
        if not isinstance(document, dict) or document.get("format") != "po":
            raise InvalidPoError("Project has no PO source document")
        raw_blocks = document.get("blocks")
        if not isinstance(raw_blocks, list):
            raise InvalidPoError("PO source document is invalid")
        blocks = cast(list[PoBlock], deepcopy(raw_blocks))
        for entry in project.entries:
            if len(entry.key_path) != 4:
                continue
            _, block_index, _, plural_index = entry.key_path
            block = blocks[int(block_index)]
            if isinstance(block, dict) and isinstance(block.get("msgstr"), dict):
                translations = cast(dict[str, object], block["msgstr"])
                translations[str(plural_index)] = entry.translation or ""
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "\n\n".join(self._format_block(block) for block in blocks) + "\n",
            encoding="utf-8",
        )

    def _parse_block(self, text: str) -> PoBlock:
        block: PoBlock = {"comments": [], "msgstr": {}}
        active_field: str | None = None
        active_plural = "0"
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith("#"):
                comments = block["comments"]
                if isinstance(comments, list):
                    comments.append(raw_line)
                continue
            match = self._DIRECTIVE.match(line)
            if match:
                directive, plural_index, quoted = match.groups()
                value = self._decode(quoted)
                if directive.startswith("msgstr"):
                    active_field = "msgstr"
                    active_plural = plural_index or "0"
                    translations = block["msgstr"]
                    if isinstance(translations, dict):
                        translations[active_plural] = value
                else:
                    active_field = directive
                    block[directive] = value
                continue
            if line.startswith('"') and active_field is not None:
                value = self._decode(line)
                if active_field == "msgstr":
                    translations = block["msgstr"]
                    if isinstance(translations, dict):
                        current_value = str(translations.get(active_plural, ""))
                        translations[active_plural] = current_value + value
                else:
                    block[active_field] = str(block.get(active_field, "")) + value
                continue
            if line:
                raise InvalidPoError(f"Unsupported PO line: {raw_line}")
        return block

    @staticmethod
    def _decode(value: str) -> str:
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as error:
            raise InvalidPoError("Invalid PO quoted string") from error
        if not isinstance(decoded, str):
            raise InvalidPoError("PO value must be a string")
        return decoded

    @staticmethod
    def _format_block(block: object) -> str:
        if not isinstance(block, dict):
            raise InvalidPoError("PO block is invalid")
        lines = [str(comment) for comment in block.get("comments", [])]
        for field in ("msgctxt", "msgid", "msgid_plural"):
            value = block.get(field)
            if isinstance(value, str):
                lines.append(f"{field} {json.dumps(value, ensure_ascii=False)}")
        translations = block.get("msgstr")
        if isinstance(translations, dict):
            plural = "msgid_plural" in block or set(translations) != {"0"}
            for index, value in sorted(
                translations.items(), key=lambda item: int(item[0])
            ):
                directive = f"msgstr[{index}]" if plural else "msgstr"
                lines.append(f"{directive} {json.dumps(str(value), ensure_ascii=False)}")
        return "\n".join(lines)
