[English](README.md) | [Русский](README.ru.md)

# LocaForge

LocaForge is a local-first desktop CAT platform for translating games, applications,
and software with local language models. Source files stay on the user's computer and
are never modified in place.

> The project is under active development. Current version: `0.4.2`.

## Features

- format-preserving import and export for JSON, CSV/TSV, Gettext PO, and XML;
- multi-file, mixed-format projects in portable SQLite/ZIP-based `.lfproj` containers;
- manual and batch editing, glossary, translation memory, revision history, and review;
- local translation and AI review through Ollama, with separate model selection;
- placeholder protection, validation, persistent Undo/Redo, and project-wide history;
- optional structured project profiles for richer model context;
- a PySide6 desktop interface with English, Russian, and user-provided localizations.

## Requirements

- Python 3.12 or newer when running from source;
- [Ollama](https://ollama.com/) for local AI translation and review.

## Install and run

### Windows portable build

Download `LocaForge-0.4.2-windows-x64.zip` from the
[latest release](https://github.com/SuperMan4eg/locaforge/releases/latest), extract it,
and run `LocaForge.exe`. Python is included; Ollama is installed separately.

### From source

```powershell
git clone https://github.com/SuperMan4eg/locaforge.git
cd locaforge
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
locaforge
```

You can also start the application with `python -m locaforge`.

## Model settings

Application settings define the global Ollama models, prompts, reasoning modes, timeout,
and batch size. A project inherits the current global values unless **Override global
model settings** is enabled in Project Settings. Enabling the override copies the current
effective values into the project; later global changes no longer affect it. Disabling the
override resumes inheritance. See the [developer guide](docs/development.md#model-settings-inheritance)
for persistence and migration details.

## Custom interface languages

Language packages are JSON files loaded from the user localization directory. Start with
the generated `template.json`, translate its messages without changing their keys or named
parameters, save it under a new name, then reload and validate it in Settings. The complete
format and troubleshooting guide is in [Custom localization](docs/localization.md).

## Diagnostics and privacy

The Logs panel provides **Copy diagnostics** for support requests. The report contains application,
Python, PySide, Qt, and OS versions plus aggregate project counts and formats. It never includes
project names, filesystem paths, source strings, translations, prompts, or log contents. Review any
manually copied log messages separately before sharing them. After an unexpected application error,
the report also includes the short incident ID shown in the error dialog so support can correlate it
with the local traceback without putting that traceback on the clipboard.

## Development

```powershell
$env:PYTHONPATH = "src"
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest
python -m ruff check src tests
python -m mypy src
python scripts/check_docs.py
```

CI runs these quality checks on Python 3.12 and 3.13, builds Python packages and a
smoke-tested Windows portable archive, and verifies documentation language pairs and links.

## Architecture and project documentation

The code follows Clean Architecture; dependencies point inward:

```text
Presentation ─┐
Infrastructure├──> Application ───> Domain
App/bootstrap ─┘
```

Read the [architecture](docs/architecture.md), [developer guide](docs/development.md),
[MVP contracts](contracts/mvp-contracts.md), [JSON round-trip contract](contracts/json-round-trip.md),
and [changelog](CHANGELOG.md). Every user and developer document is available in English
and Russian; use the language switch at the top of each page.

## License

Licensed under the [Apache License 2.0](LICENSE).
