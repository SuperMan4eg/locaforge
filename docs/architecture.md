# Архитектура LocaForge 0.3

## Назначение

LocaForge — локальная CAT-платформа для перевода JSON, CSV/TSV, Gettext PO и XML.
Приложение импортирует исходный документ в переносимый проект `.lfproj`, позволяет
редактировать и проверять переводы, использовать локальную модель Ollama, glossary,
translation memory и AI review, после чего восстанавливает исходный формат при
экспорте. Исходные файлы пользователя не изменяются.

## Правило зависимостей

Зависимости направлены только внутрь:

```text
Presentation ─┐
Infrastructure├──> Application ───> Domain
App/bootstrap ─┘
```

- `domain` содержит сущности, value objects и правила предметной области.
- `application` содержит сценарии использования, DTO, фасад `ProjectWorkspace` и
  порты внешних зависимостей.
- `infrastructure` реализует форматы файлов, SQLite-хранилища, ZIP-контейнер и
  Ollama-клиент.
- `presentation` содержит PySide6 widgets, models, фоновые workers и контроллеры
  пользовательских сценариев; бизнес-правила остаются в application/domain.
- `app` связывает конкретные реализации и запускает приложение.

`domain` и `application` не импортируют PySide6, sqlite3, HTTP-клиенты или код
конкретных парсеров.

## Структура пакетов

```text
src/locaforge/
  app/                    # composition root, logging, запуск приложения
  domain/                 # Project, TranslationEntry, glossary, TM, history
  application/
    ports/                # форматы, persistence, LLM, glossary и TM
    use_cases/            # import/export, edit, translate, validate, review
    dto/                  # результаты перевода, review, validation и project
  infrastructure/
    formats/              # JSON, CSV/TSV, PO, XML и glossary CSV
    persistence/          # SQLite, .lfproj, glossary и translation memory
    llm/                  # Ollama translation/review client
  presentation/
    *_controller.py       # UI orchestration по отдельным сценариям
    *_worker.py           # фоновые Qt-потоки
    main_window.py        # композиция widgets, actions и контроллеров
```

## Основные сценарии

1. Импорт JSON, CSV/TSV, PO или XML создаёт `Project` и сохраняет исходную
   document model для обратного экспорта.
2. Ручное и пакетное редактирование меняет только рабочий проект, записывает
   историю и обновляет translation memory.
3. Batch translation защищает placeholders, вызывает Ollama, валидирует каждый
   ответ и сохраняет частично успешный результат.
4. Validation проверяет структуру, placeholders, длину, glossary, согласованность
   и другие QA-правила.
5. AI review добавляет отдельные issues, не изменяя перевод автоматически.
6. Экспорт выполняет preflight и восстанавливает формат импортированного документа.

Долгие операции выполняются `QThread` workers. Контроллеры presentation управляют
их жизненным циклом, отменой, прогрессом и обновлением UI, а изменение данных всегда
проходит через `ProjectWorkspace` и application use cases.

## Проект и сохранение

`.lfproj` — ZIP-контейнер, а не SQLite-база, изменяемая внутри архива. При открытии:

1. контейнер распаковывается в управляемый рабочий каталог;
2. SQLite используется только из этого каталога;
3. сохранение формирует новый контейнер во временном файле;
4. временный файл атомарно заменяет целевой `.lfproj`;
5. предыдущая версия сохраняется как резервная копия.

Autosave использует тот же безопасный путь сохранения. Несохранённое состояние
отражается в `Project.dirty`.

## Форматы и расширение

Каждый формат реализует application-порты importer/exporter. Импорт сохраняет
метаданные, необходимые для round trip, а экспорт заменяет только переводимые
значения. Добавление формата не должно менять domain или UI-сценарии проекта.

Ollama, persistence, glossary и translation memory также подключены через порты.
Новый LLM backend или хранилище реализует соответствующий порт и регистрируется в
`app/bootstrap.py`.

## Presentation

`MainWindow` является composition view: создаёт widgets и actions, после чего
передаёт их специализированным контроллерам. Отдельные контроллеры управляют
project I/O, import mappings, фильтрами, QA, batch translation, AI review,
validation, translation memory, glossary, history, recent projects и model pull.

Такое разделение позволяет тестировать orchestration без запуска полного окна.
Дополнительные smoke-тесты создают реальный `MainWindow` в offscreen-режиме и
проверяют совместимость всех сигналов и контроллеров.

## Границы версии 0.3

Один проект содержит одну языковую пару и один или несколько импортированных
документов разных поддерживаемых форматов. `ProjectDocument` хранит исходный путь,
формат и document model для round trip; каждая `TranslationEntry` принадлежит
документу через `document_id`.

Контейнер формата 2 автоматически открывает проекты формата 1 и мигрирует старую
SQLite-схему. Основной LLM backend — Ollama. Результаты основной модели и reviewer
хранятся отдельно от активного экспортируемого перевода. Batch translation создаёт
операционный снимок для транзакционного Undo.

Плагины, командная работа, Redo и альтернативные LLM backend'ы остаются последующими
расширениями.
