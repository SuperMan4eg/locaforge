# LocaForge

LocaForge — локальная desktop CAT-платформа для перевода игр, приложений и
программного обеспечения с помощью локальных языковых моделей. Исходные файлы
не отправляются во внешние сервисы и не изменяются напрямую.

> Проект находится в активной разработке. Текущая версия — `0.1.0`.

## Возможности

- импорт и экспорт JSON, CSV, PO и XML с сохранением структуры;
- переносимые проекты `.lfproj` на базе SQLite и ZIP-контейнера;
- ручное и пакетное редактирование переводов;
- локальный перевод через Ollama;
- защита placeholders и проверка результатов перевода;
- glossary, translation memory, история изменений и review workflow;
- desktop-интерфейс на PySide6.

## Требования

- Python 3.12 или новее;
- [Ollama](https://ollama.com/) — для локального AI-перевода.

## Установка и запуск

### Готовая сборка для Windows

Скачайте `LocaForge-0.1.0-windows-x64.zip` на странице
[последнего релиза](https://github.com/SuperMan4eg/locaforge/releases/latest),
распакуйте архив и запустите `LocaForge.exe`. Устанавливать Python не требуется.
Для локального AI-перевода Ollama устанавливается отдельно.

### Установка из исходного кода

```powershell
git clone https://github.com/SuperMan4eg/locaforge.git
cd locaforge
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
locaforge
```

Приложение также можно запустить как Python-модуль:

```powershell
python -m locaforge
```

## Разработка

```powershell
$env:PYTHONPATH = "src"
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest
python -m ruff check src tests
python -m mypy src
```

CI выполняет тесты, Ruff и mypy на Python 3.12 и 3.13, а также проверяет сборку
wheel и source distribution.

## Архитектура

Проект следует Clean Architecture; зависимости направлены внутрь:

```text
Presentation ─┐
Infrastructure├──> Application ───> Domain
App/bootstrap ─┘
```

- `domain` — сущности и правила предметной области;
- `application` — сценарии использования, DTO и порты;
- `infrastructure` — форматы файлов, SQLite, контейнер проекта и Ollama;
- `presentation` — PySide6 UI без бизнес-логики;
- `app` — сборка зависимостей и запуск приложения.

Подробности: [архитектура](docs/architecture.md),
[руководство разработчика](docs/development.md) и [контракты MVP](contracts/mvp-contracts.md).

## Принципы проекта

- полностью локальная работа и контроль данных пользователем;
- исходные файлы остаются неизменными;
- экспорт восстанавливает исходный формат;
- бизнес-логика отделена от GUI, хранилища и LLM backend;
- расширяемость через явные интерфейсы и тестируемые контракты.

## Лицензия

LocaForge распространяется по свободной лицензии
[Apache License 2.0](LICENSE). Она разрешает использовать, изменять и
распространять проект, в том числе в коммерческих целях, при соблюдении условий
лицензии и сохранении уведомлений об авторстве.
