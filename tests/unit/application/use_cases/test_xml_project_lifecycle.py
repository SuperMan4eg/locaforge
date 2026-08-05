from pathlib import Path

from locaforge.application.use_cases.create_project_from_xml import CreateProjectFromXml
from locaforge.application.use_cases.edit_translation import EditTranslation
from locaforge.application.use_cases.export_project_xml import ExportProjectXml
from locaforge.application.use_cases.open_project_file import OpenProjectFile
from locaforge.application.use_cases.save_project_file import SaveProjectFile
from locaforge.infrastructure.formats.xml_format import XmlFileFormat
from locaforge.infrastructure.persistence.lfproj_container import LfprojContainer
from locaforge.infrastructure.persistence.sqlite_project_repository_factory import (
    SQLiteProjectRepositoryFactory,
)


def test_open_edit_save_reopen_and_export_xml_project(tmp_path: Path) -> None:
    source_path = tmp_path / "dialog.xml"
    source_path.write_text(
        '<dialog><line id="welcome">Hello</line></dialog>', encoding="utf-8"
    )
    project_path = tmp_path / "dialog.lfproj"
    repository_factory = SQLiteProjectRepositoryFactory()
    xml_format = XmlFileFormat()
    CreateProjectFromXml(
        xml_format,
        LfprojContainer(tmp_path / "create-work"),
        repository_factory,
    ).execute(source_path, project_path, "en", "ru")

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
    destination = tmp_path / "dialog_ru.xml"
    ExportProjectXml(xml_format, repository_factory).execute(
        reopened.session, destination
    )

    assert "<line id=\"welcome\">Привет</line>" in destination.read_text(
        encoding="utf-8"
    )
    assert reopened.session.metadata["source_format"] == "xml"
