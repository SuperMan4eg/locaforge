[English](development.md) | [Русский](development.ru.md)

# Руководство разработчика

## Локальная настройка

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:PYTHONPATH = "src"
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest
python -m ruff check src tests
python -m mypy src
python scripts/check_docs.py
```

Запустите приложение командой `locaforge` или `python -m locaforge`.

## Наследование настроек моделей

`ApplicationSettings.model_settings` — глобальный пользовательский профиль. Он содержит
модель перевода, необязательную модель reviewer, режимы reasoning, timeout, размер пакета и
system prompts. Профиль хранится в настройках Qt и передаётся `ProjectWorkspace` при запуске.

Каждый проект также хранит `model_settings` и `model_settings_override_enabled`:

- при выключенном override `resolve_model_settings()` возвращает текущий глобальный профиль;
- включение override сначала копирует текущий эффективный профиль в проект;
- при включённом override используются проектные значения, не зависящие от будущих глобальных изменений;
- изменение настроек моделей открытого проекта включает его override;
- отключение override возвращает живое наследование, не удаляя сохранённый снимок проекта;
- старые проекты с собственными настройками мигрируют с включённым override, а новые проекты
  по умолчанию наследуют глобальные настройки.

URL сервера Ollama относится к приложению. Проектные настройки моделей сохраняются в SQLite
внутри `.lfproj`. Такое разделение сохраняет переносимость проекта и позволяет каждой
установке использовать собственный локальный endpoint Ollama.

## Соглашение о документации

Английская версия является основной на GitHub. У каждого Markdown-документа, кроме `LICENSE`,
должны быть английский файл и пара `.ru.md`. Оба начинаются переключателем `English | Русский`,
а ссылки ведут на язык читателя, если целевой перевод существует. Перед commit запустите
`python scripts/check_docs.py`; CI проверяет пары, переключатели и локальные ссылки.

## Portable-сборка Windows

```powershell
python -m pip install -e ".[build]"
.\scripts\build_windows.ps1
```

Скрипт создаёт `dist/LocaForge/LocaForge.exe` и формирует архив с версией. Исполняемый файл
поддерживает две проверки сборки: `--smoke-test` запускает и собирает интерфейс, а `--self-test`
создаёт, редактирует, сохраняет, повторно открывает и экспортирует изолированный JSON-проект.

## CI и релизы

CI запускает Ruff, mypy и pytest на Python 3.12 и 3.13, проверяет документацию, собирает wheel
и sdist, а также запускает обе проверки собранного Windows-архива. Тег `v<project.version>` публикует GitHub
Release с пакетами, portable-архивом и SHA-256 checksums.

## Checklist изменений

- сохраняйте независимость domain и application от фреймворков;
- добавляйте тесты на минимально достаточном уровне;
- обновляйте обе языковые версии затронутой документации и changelog;
- сохраняйте round-trip контракты import/export и совместимость миграций.
