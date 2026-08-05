# Контракты MVP

Этот документ фиксирует поведение портов до реализации. Реализации могут
отличаться, но не должны менять эти семантики.

## Сущности

### TranslationEntry

| Поле | Тип | Правило |
| --- | --- | --- |
| `id` | UUID/str | Стабильно внутри проекта. |
| `key_path` | tuple[str \| int, ...] | Путь к строке в исходном JSON. |
| `source` | str | Исходный текст; после импорта неизменяем. |
| `translation` | str \| None | `None` означает отсутствие перевода. |
| `status` | enum | `untranslated`, `translated`, `needs_review`, `approved`, `error`. |
| `locked` | bool | Заблокированную запись не меняют ни UI, ни batch-перевод. |
| `context` | str \| None | Контекст из импорта или пользовательский. |
| `max_length` | int \| None | Ограничение в символах при наличии. |
| `placeholders` | sequence[str] | Выделены до отправки модели. |

Изменение `translation` вручную переводит запись в `needs_review`, кроме
явного действия approve. Пустая строка не равна отсутствующему переводу.

### Project

`Project` содержит идентификатор, имя, source/target language, список файлов,
записей, настройки модели, схему импортированного документа и флаг `dirty`.
Ни один use case не изменяет исходный JSON-файл пользователя.

## Порты application

### ProjectRepository

```text
create(project) -> None
get(project_id) -> Project
save(project) -> None
list_entries(project_id, filter) -> Page[TranslationEntry]
get_entry(project_id, entry_id) -> TranslationEntry
update_entry(project_id, entry) -> None
```

`save` и `update_entry` выполняются транзакционно. Не найденный объект —
`ProjectNotFound` или `EntryNotFound`, а не `None`.

### ProjectContainer

```text
open(path) -> OpenProject
save(open_project, destination) -> None
```

`open` распаковывает `.lfproj` в рабочую директорию. `save` создаёт валидный
контейнер атомарно и не портит прежний файл при ошибке.

### JsonImporter / JsonExporter

```text
import_file(path, source_language, target_language) -> ImportedProject
export_file(project, destination) -> None
```

Импортер создаёт записи только для JSON string values. Экспортер изменяет только
те строковые leaf values, для которых существует непустой `translation`; все
остальные значения сохраняет семантически идентичными.

### LLMClient

```text
translate(request: TranslationRequest) -> TranslationResponse
health_check() -> ModelHealth
```

`TranslationRequest` содержит выбранную модель, языки, набор записей, prompt и
тайм-аут. Ответ соотносит результат с `entry_id`; порядок не считается контрактом.
Backend не должен сам сохранять результаты и не должен видеть SQLite.

### TranslationService

```text
translate_batch(project_id, entry_ids, options) -> BatchResult
```

Сервис пропускает `locked` и `approved` записи по умолчанию, защищает placeholders,
валидирует ответ и сохраняет только валидные результаты. Некорректные записи
возвращаются в `BatchResult.errors`, не теряя уже валидных результатов пакета.

## Ошибки

Ошибки должны быть различимы программно: `InvalidJson`, `UnsupportedJsonShape`,
`ProjectNotFound`, `EntryNotFound`, `ProjectBusy`, `ModelUnavailable`,
`ModelTimeout`, `InvalidModelResponse`, `PlaceholderMismatch`, `ExportFailed`.
В UI отображается человекочитаемое сообщение; полный технический контекст идёт
только в журнал.
