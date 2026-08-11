"""Portable `.lfproj` ZIP container implementation."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import zipfile
from pathlib import Path

from locaforge.application.project_session import ProjectSession


class ProjectContainerError(ValueError):
    """Raised when a project container cannot be opened or saved safely."""


class LfprojContainer:
    """Creates and opens ZIP-backed project working copies."""

    _DATABASE_NAME = "project.db"
    _METADATA_NAME = "metadata.json"
    _FORMAT_VERSION = 2
    _SUPPORTED_FORMAT_VERSIONS = frozenset({1, 2})
    _BACKUP_GENERATIONS = 3
    # sqlite3_backup_step holds a read lock for each batch. Keeping autosave
    # batches small lets foreground edits acquire the database between steps.
    _SNAPSHOT_PAGES_PER_STEP = 128

    def __init__(self, working_root: Path) -> None:
        self._working_root = working_root
        self._working_root.mkdir(parents=True, exist_ok=True)

    def create(self, metadata: dict[str, object] | None = None) -> ProjectSession:
        working_directory = self._new_working_directory()
        return ProjectSession(
            working_directory=working_directory,
            database_path=working_directory / self._DATABASE_NAME,
            metadata=self._normalize_metadata(metadata),
        )

    def open(self, path: Path) -> ProjectSession:
        if not path.is_file():
            raise ProjectContainerError(f"Project container {path} does not exist")

        working_directory = self._new_working_directory()
        try:
            with zipfile.ZipFile(path) as archive:
                damaged_member = archive.testzip()
                if damaged_member is not None:
                    raise ProjectContainerError(
                        f"Container member {damaged_member!r} failed its integrity check"
                    )
                member_names = set(archive.namelist())
                required_names = {self._DATABASE_NAME, self._METADATA_NAME}
                if not required_names.issubset(member_names):
                    raise ProjectContainerError("Container is missing project.db or metadata.json")
                if any(not self._is_safe_member_name(name) for name in member_names):
                    raise ProjectContainerError("Container has an unsafe file path")

                metadata = self._read_metadata(archive)
                self._extract_member(archive, self._DATABASE_NAME, working_directory)
                self._extract_member(archive, self._METADATA_NAME, working_directory)
                self._validate_database(working_directory / self._DATABASE_NAME)
        except (OSError, zipfile.BadZipFile) as error:
            shutil.rmtree(working_directory, ignore_errors=True)
            raise ProjectContainerError(f"Cannot open project container {path.name!r}") from error
        except Exception:
            shutil.rmtree(working_directory, ignore_errors=True)
            raise

        return ProjectSession(
            working_directory=working_directory,
            database_path=working_directory / self._DATABASE_NAME,
            metadata=metadata,
            container_path=path,
        )

    def save(self, session: ProjectSession, destination: Path) -> None:
        self._save_database(session, session.database_path, destination, create_backup=True)

    def save_snapshot(self, session: ProjectSession, destination: Path) -> None:
        snapshot_path = session.working_directory / "autosave-snapshot.db"
        try:
            source = sqlite3.connect(session.database_path)
            snapshot = sqlite3.connect(snapshot_path)
            try:
                source.backup(snapshot, pages=self._SNAPSHOT_PAGES_PER_STEP)
            finally:
                snapshot.close()
                source.close()
            self._save_database(session, snapshot_path, destination, create_backup=False)
        finally:
            snapshot_path.unlink(missing_ok=True)

    def _save_database(
        self,
        session: ProjectSession,
        database_path: Path,
        destination: Path,
        create_backup: bool,
    ) -> None:
        if not database_path.is_file():
            raise ProjectContainerError("Project database does not exist in the working copy")

        self._validate_database(database_path)

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = destination.with_suffix(f"{destination.suffix}.tmp")
        backup_path = destination.with_suffix(f"{destination.suffix}.bak")
        try:
            with zipfile.ZipFile(
                temporary_path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=1,
            ) as archive:
                archive.write(database_path, self._DATABASE_NAME)
                archive.writestr(
                    self._METADATA_NAME,
                    json.dumps(
                        self._normalize_metadata(session.metadata), ensure_ascii=False, indent=2
                    ),
                )
            if create_backup and destination.exists():
                self._rotate_backups(backup_path)
                shutil.copy2(destination, backup_path)
            os.replace(temporary_path, destination)
        except (OSError, TypeError, zipfile.BadZipFile) as error:
            raise ProjectContainerError(
                f"Cannot save project container to {destination}"
            ) from error
        finally:
            temporary_path.unlink(missing_ok=True)

        session.container_path = destination

    def _rotate_backups(self, newest_backup: Path) -> None:
        for generation in range(self._BACKUP_GENERATIONS - 1, 0, -1):
            source = (
                newest_backup
                if generation == 1
                else newest_backup.with_name(f"{newest_backup.name}.{generation - 1}")
            )
            destination = newest_backup.with_name(f"{newest_backup.name}.{generation}")
            if source.exists():
                os.replace(source, destination)

    @staticmethod
    def _validate_database(database_path: Path) -> None:
        try:
            connection = sqlite3.connect(database_path)
            try:
                result = connection.execute("PRAGMA quick_check").fetchall()
            finally:
                connection.close()
        except sqlite3.DatabaseError as error:
            raise ProjectContainerError("Project database failed its integrity check") from error
        if result != [("ok",)]:
            raise ProjectContainerError("Project database failed its integrity check")

    def _new_working_directory(self) -> Path:
        for index in range(1, 10_000):
            working_directory = self._working_root / f"project-{index:04d}"
            try:
                working_directory.mkdir()
            except FileExistsError:
                continue
            return working_directory
        raise ProjectContainerError("Cannot allocate a project working directory")

    def _read_metadata(self, archive: zipfile.ZipFile) -> dict[str, object]:
        try:
            with archive.open(self._METADATA_NAME) as metadata_file:
                metadata = json.loads(metadata_file.read().decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProjectContainerError("Container metadata is invalid") from error
        if not isinstance(metadata, dict):
            raise ProjectContainerError("Container metadata must be a JSON object")
        return self._normalize_metadata(metadata)

    def _normalize_metadata(self, metadata: dict[str, object] | None) -> dict[str, object]:
        normalized = dict(metadata or {})
        version = normalized.get("format_version", self._FORMAT_VERSION)
        if version not in self._SUPPORTED_FORMAT_VERSIONS:
            raise ProjectContainerError(f"Unsupported project format version: {version!r}")
        normalized["format_version"] = self._FORMAT_VERSION
        return normalized

    @staticmethod
    def _is_safe_member_name(name: str) -> bool:
        member_path = Path(name)
        return not member_path.is_absolute() and ".." not in member_path.parts

    @staticmethod
    def _extract_member(archive: zipfile.ZipFile, member_name: str, destination: Path) -> None:
        with archive.open(member_name) as source, (destination / member_name).open("wb") as target:
            shutil.copyfileobj(source, target)
