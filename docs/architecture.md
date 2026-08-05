# Архитектура LocaForge (MVP)

## Цель

MVP переводит JSON-файл через локальную модель Ollama, позволяет отредактировать
результат и экспортирует JSON, не меняя его исходную структуру. Архитектура
сохраняет эту вертикаль независимой от PySide6, SQLite и конкретного LLM backend.

## Правило зависимостей

Зависимости направлены только внутрь:

```text
Presentation ─┐
Infrastructure├──> Application ───> Domain
App/bootstrap ─┘
```

- `domain` содержит сущности, value objects и правила предметной области.
- `application` содержит сценарии использования и порты (Protocol/ABC).
- `infrastructure` реализует порты: SQLite, ZIP, JSON, Ollama, filesystem.
- `presentation` преобразует действия пользователя в application-команды и
  отображает их результат; бизнес-правил в ней нет.
- `app` — единственное место, которое импортирует concrete implementations и
  связывает зависимости.

`domain` и `application` не импортируют PySide6, sqlite3, HTTP-клиенты, Ollama
SDK или код парсеров.

## Предлагаемые пакеты

```text
src/locaforge/
  app/                 # composition root, config, запуск приложения
  domain/              # Project, TranslationEntry, статусы и инварианты
  application/
    ports/             # интерфейсы внешних зависимостей
    use_cases/         # import, save, translate, edit, export
    dto/               # входные команды и выходные модели
  infrastructure/
    persistence/       # SQLite и файловая рабочая копия проекта
    formats/           # JSON importer/exporter
    llm/               # OllamaClient
  presentation/        # PySide6: view models, widgets, presenters
  shared/              # только технические утилиты без бизнес-правил
```

## Основные сценарии MVP

1. `ImportJson`: JSON превращается в `Project` и набор `TranslationEntry`.
2. `EditTranslation`: пользователь меняет перевод одной незаблокированной записи.
3. `TranslateBatch`: application формирует пакет, защищает placeholders, вызывает
   `LLMClient`, валидирует и сохраняет результат.
4. `SaveProject`: состояние сохраняется атомарно.
5. `ExportJson`: exporter берёт исходный document model и подставляет переводы.

Каждый use case — обычный синхронный интерфейс на уровне application. Долгие
операции запускает presentation/worker, но отмена и изменения состояния проходят
через application use cases.

## Проект и сохранение

`.lfproj` — переносимый ZIP-контейнер, но не рабочая база SQLite. При открытии:

1. контейнер распаковывается в управляемый временный рабочий каталог;
2. SQLite используется только из этого каталога;
3. сохранение записывает новый контейнер во временный файл;
4. временный файл атомарно заменяет целевой `.lfproj`;
5. перед заменой сохраняется одна резервная копия предыдущей версии.

Это исключает изменение SQLite внутри ZIP и снижает риск повреждения проекта при
сбое. Несохранённое состояние явно отражается в `Project.dirty`.

## Ошибки и события

Application возвращает типизированные ошибки (`ImportError`, `ValidationError`,
`ModelUnavailable`, `ProjectConflict`) с безопасным текстом для UI и технической
причиной для журналирования. События нужны только для уведомления наблюдателей;
они не заменяют вызовы use cases и не являются источником истины.

Для MVP достаточно: `ProjectImported`, `ProjectSaved`, `BatchStarted`,
`BatchFinished`, `TranslationValidated`, `ProjectExported`.

## Неподвижные границы MVP

В первой версии поддерживается один JSON-документ, один целевой язык и Ollama.
Translation Memory, Glossary, плагины, XML и иные backend'ы остаются будущими
расширениями: контракты не должны требовать их реализации для запуска MVP.
