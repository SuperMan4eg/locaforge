"""Factory for SQLite project repositories."""

from pathlib import Path

from locaforge.infrastructure.persistence.sqlite_project_repository import SQLiteProjectRepository


class SQLiteProjectRepositoryFactory:
    def create(self, database_path: Path) -> SQLiteProjectRepository:
        return SQLiteProjectRepository(database_path)
