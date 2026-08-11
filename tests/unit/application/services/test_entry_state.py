from locaforge.application.services.entry_state import EntryStateService
from locaforge.domain.entry import EntryStatus, TranslationEntry
from locaforge.domain.project import Project
from locaforge.domain.translation_memory import TranslationMemoryRecord


class Repository:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.operations: list[tuple[object, ...]] = []

    def get(self, _project_id: str) -> Project:
        return self.project

    def get_entry(self, _project_id: str, entry_id: str) -> TranslationEntry:
        return self.project.get_entry(entry_id)

    def list_validation_issues(self, _project_id: str) -> tuple[()]:
        return ()

    def update_entry(self, _project_id: str, _entry: TranslationEntry) -> None:
        pass

    def record_translation_operation(self, *args: object) -> None:
        self.operations.append(args)


class Memory:
    def __init__(self) -> None:
        self.records: list[TranslationMemoryRecord] = []

    def store(self, record: TranslationMemoryRecord) -> None:
        self.records.append(record)


def make_project() -> Project:
    entry = TranslationEntry(
        "entry-1", ("text",), "Hello", context="Button label"
    )
    entry.set_translation("Привет")
    return Project("p", "Demo", "en", "ru", entries=[entry])


def test_approval_is_undoable_and_stored_in_translation_memory() -> None:
    project = make_project()
    repository = Repository(project)
    memory = Memory()
    service = EntryStateService(memory)  # type: ignore[arg-type]

    entry = service.set_approval(  # type: ignore[arg-type]
        repository, project, "entry-1", True
    )

    assert entry.status is EntryStatus.APPROVED
    assert repository.operations[0][3] == "Approve translation"
    assert memory.records == [
        TranslationMemoryRecord("en", "ru", "Hello", "Привет", "Button label")
    ]


def test_lock_and_unlock_use_distinct_history_labels() -> None:
    project = make_project()
    repository = Repository(project)
    service = EntryStateService(None)

    service.set_locked(repository, project, "entry-1", True)  # type: ignore[arg-type]
    service.set_locked(repository, project, "entry-1", False)  # type: ignore[arg-type]

    assert [operation[3] for operation in repository.operations] == [
        "Lock translation",
        "Unlock translation",
    ]
