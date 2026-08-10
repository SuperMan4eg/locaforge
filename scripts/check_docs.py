"""Validate bilingual documentation pairs, language switches, and local links."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DOC_DIRS = (ROOT / "docs", ROOT / "contracts")
ROOT_DOC_PATTERNS = ("README*.md", "CHANGELOG*.md")
LINK = re.compile(r"(?<!!)\[[^]]*]\(([^)]+)\)")
SWITCH = re.compile(r"^\[English]\([^)]+\) \| \[Русский]\([^)]+\)$")


def documentation_files() -> list[Path]:
    files: list[Path] = []
    for pattern in ROOT_DOC_PATTERNS:
        files.extend(ROOT.glob(pattern))
    for directory in DOC_DIRS:
        files.extend(sorted(directory.glob("*.md")))
    return sorted(files)


def english_peer(path: Path) -> Path:
    return path.with_name(path.name.removesuffix(".ru.md") + ".md")


def russian_peer(path: Path) -> Path:
    return path.with_name(path.stem + ".ru.md")


def main() -> int:
    errors: list[str] = []
    files = documentation_files()
    for path in files:
        relative = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        first_line = text.splitlines()[0] if text else ""
        if not SWITCH.fullmatch(first_line):
            errors.append(f"{relative}: missing language switch on the first line")

        peer = english_peer(path) if path.name.endswith(".ru.md") else russian_peer(path)
        if not peer.is_file():
            errors.append(f"{relative}: missing language peer {peer.relative_to(ROOT)}")

        for raw_target in LINK.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            local_part = unquote(target.split("#", 1)[0].split("?", 1)[0])
            resolved = (path.parent / local_part).resolve()
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                errors.append(f"{relative}: link escapes repository: {target}")
                continue
            if not resolved.exists():
                errors.append(f"{relative}: broken local link: {target}")

    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Documentation validation passed for {len(files)} bilingual files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
