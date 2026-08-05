from pathlib import Path

from locaforge.application.ports.csv_format import CsvFieldMapping
from locaforge.application.use_cases.create_project_from_csv import CreateProjectFromCsv
from locaforge.application.use_cases.edit_translation import EditTranslation
from locaforge.application.use_cases.export_project_csv import ExportProjectCsv
from locaforge.application.use_cases.open_project_file import OpenProjectFile
from locaforge.application.use_cases.save_project_file import SaveProjectFile
from locaforge.infrastructure.formats.csv_format import CsvFileFormat
from locaforge.infrastructure.persistence.lfproj_container import LfprojContainer
from locaforge.infrastructure.persistence.sqlite_project_repository_factory import (
    SQLiteProjectRepositoryFactory,
)


def test_open_edit_save_reopen_and_export_csv_project(tmp_path: Path) -> None:
    source_path = tmp_path / "strings.csv"
    source_path.write_text(
        "key;source;target;category\nwelcome;Hello;;ui\n",
        encoding="utf-8",
    )
    project_path = tmp_path / "strings.lfproj"
    repository_factory = SQLiteProjectRepositoryFactory()
    csv_format = CsvFileFormat()
    CreateProjectFromCsv(
        csv_format,
        LfprojContainer(tmp_path / "create-work"),
        repository_factory,
    ).execute(
        source_path,
        project_path,
        "en",
        "ru",
        CsvFieldMapping("source", "target", "key"),
    )

    open_container = LfprojContainer(tmp_path / "open-work")
    opened = OpenProjectFile(open_container, repository_factory).execute(project_path)
    repository = repository_factory.create(opened.session.database_path)
    EditTranslation(repository).execute(
        opened.project.id, opened.project.entries[0].id, "Привет"
    )
    SaveProjectFile(open_container, repository_factory).execute(opened.session)

    reopened = OpenProjectFile(
        LfprojContainer(tmp_path / "reopen-work"), repository_factory
    ).execute(project_path)
    destination = tmp_path / "strings_ru.csv"
    ExportProjectCsv(csv_format, repository_factory).execute(
        reopened.session, destination
    )

    exported = destination.read_text(encoding="utf-8-sig")
    assert "welcome;Hello;Привет;ui" in exported
    assert reopened.session.metadata["source_format"] == "csv"
