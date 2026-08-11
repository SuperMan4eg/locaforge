[English](development.md) | [Русский](development.ru.md)

# Development guide

## Local setup

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

Run the app with `locaforge` or `python -m locaforge`.

## Model settings inheritance

`ApplicationSettings.model_settings` is the user-scoped global profile. It contains the
translation model, optional reviewer model, reasoning modes, timeout, batch size, and system
prompts. It is stored in Qt application settings and supplied to `ProjectWorkspace` at startup.

Every project also stores `model_settings` and `model_settings_override_enabled`:

- with the override disabled, `resolve_model_settings()` returns the current global profile;
- enabling the override first copies the current effective profile into the project;
- with the override enabled, project values are used and later global edits do not affect it;
- editing model settings for an open project enables its override;
- disabling the override resumes live inheritance without deleting the stored project snapshot;
- legacy projects that already stored model settings are migrated with the override enabled,
  while newly created projects inherit globals by default.

The Ollama server URL is application-scoped. Project model settings are persisted inside the
`.lfproj` SQLite database. This split keeps projects portable while allowing each installation
to choose its local Ollama endpoint.

## Documentation convention

English is canonical on GitHub. For every Markdown document except `LICENSE`, keep an English
file and a `.ru.md` peer. Both begin with an `English | Русский` switch, and links should stay
within the reader's language whenever a translated target exists. Run `python scripts/check_docs.py`
before committing; CI enforces pairs, switches, and valid local links.

## Windows portable build

```powershell
python -m pip install -e ".[build]"
.\scripts\build_windows.ps1
```

The script creates `dist/LocaForge/LocaForge.exe` and the versioned ZIP archive. The executable
supports two build checks: `--smoke-test` launches and composes the UI, while `--self-test`
creates, edits, saves, reopens, and exports an isolated JSON project.

## Continuous integration and releases

Tests are split into three execution layers. The fast layer excludes Qt, SQLite, containers,
and format I/O; integration tests may run in parallel, while GUI tests remain sequential:

```powershell
python -m pytest -m unit -n auto --durations=10
python -m pytest -m integration -n auto --durations=10
python -m pytest -m gui --durations=10
```

Run `python -m pytest` when a single full, sequential verification is preferable. CI starts the
three layers as separate jobs and reports their slowest tests.

CI runs Ruff, mypy, and fast unit tests on Python 3.12 and 3.13; runs integration and GUI tests
on Python 3.12; checks documentation; builds wheel and sdist; and runs both packaged build checks
on the Windows archive. A tag matching `v<project.version>` publishes a GitHub Release with
packages, the portable archive, and SHA-256 checksums.

## Change checklist

- keep domain and application independent of frameworks;
- add tests at the lowest useful layer;
- update both language versions of affected documentation and the changelogs;
- preserve import/export round-trip contracts and migration compatibility.
