"""Normalize files and folders selected for the unified import workflow."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

SUPPORTED_IMPORT_SUFFIXES = frozenset({".json", ".csv", ".tsv", ".po", ".xml"})


def collect_import_files(paths: Iterable[Path]) -> tuple[Path, ...]:
    """Return supported files from explicit paths and recursively selected folders."""
    discovered: dict[str, Path] = {}
    for raw_path in paths:
        path = Path(raw_path)
        candidates = path.rglob("*") if path.is_dir() else (path,)
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.lower() not in SUPPORTED_IMPORT_SUFFIXES:
                continue
            resolved = candidate.resolve(strict=False)
            discovered[str(resolved).casefold()] = resolved
    return tuple(sorted(discovered.values(), key=lambda item: str(item).casefold()))


def duplicate_import_names(paths: Iterable[Path]) -> frozenset[str]:
    names: set[str] = set()
    duplicates: set[str] = set()
    for path in paths:
        normalized = path.name.casefold()
        if normalized in names:
            duplicates.add(path.name)
        names.add(normalized)
    return frozenset(duplicates)


def project_import_paths(
    files: Iterable[Path], selected_paths: Iterable[Path]
) -> dict[Path, str]:
    """Map discovered files to stable project-relative POSIX paths."""
    roots = tuple(
        path.resolve(strict=False)
        for path in selected_paths
        if Path(path).is_dir()
    )
    result: dict[Path, str] = {}
    for file_path in files:
        resolved = file_path.resolve(strict=False)
        containing_roots = tuple(root for root in roots if resolved.is_relative_to(root))
        if containing_roots:
            root = max(containing_roots, key=lambda item: len(item.parts))
            relative = resolved.relative_to(root)
        else:
            relative = Path(resolved.name)
        result[resolved] = relative.as_posix()
    return result


def duplicate_project_paths(paths: Iterable[str]) -> frozenset[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for path in paths:
        normalized = path.casefold()
        if normalized in seen:
            duplicates.add(path)
        seen.add(normalized)
    return frozenset(duplicates)
