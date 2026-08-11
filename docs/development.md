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

## Performance baseline

Run the reproducible local benchmark before and after performance-sensitive changes:

```powershell
$env:PYTHONPATH = "src"
$env:QT_QPA_PLATFORM = "offscreen"
python scripts/benchmark_performance.py `
  --json benchmark.json `
  --markdown benchmark.md
```

The default matrix creates isolated projects with 1,000, 10,000, and 50,000 entries and records
median and nearest-rank p95 timings over five measured runs after one warm-up. It covers cold UI
composition, entry lookup, statistics, table search and document filtering, table updates, project
opening, editing, Undo/Redo, validation, full repository writes, manual `.lfproj` saves, autosaves,
translation-memory matching, and cached batch glossary matching. Fixtures live in a temporary
directory and are deleted after the
run. Results include Python, PySide, SQLite, OS, and processor metadata for meaningful comparisons.

Use the smoke-sized run while changing the benchmark itself:

```powershell
python scripts/benchmark_performance.py --quick --skip-startup
```

An Ollama measurement is opt-in because it loads and runs the selected local model:

```powershell
python scripts/benchmark_performance.py `
  --ollama-url http://127.0.0.1:11434 `
  --ollama-model qwen3:8b `
  --ollama-batch-sizes 5 10 20 40 `
  --ollama-keep-alive-seconds 300 `
  --json benchmark-with-ollama.json
```

The Ollama result retains server-reported load, prompt-evaluation, generation, and token-count
metrics, plus generated tokens per second and translated entries per minute for each batch size.
Use `-1` to keep the model loaded or `0` to unload it after every request when measuring cold-load
behavior. Do not compare reports from different power modes, background workloads, Python versions,
or model configurations. Benchmarks are diagnostic and deliberately have no timing thresholds in CI.
The checked-in reference for the current development machine is
`benchmarks/baseline-windows-cpython314.json`.

The stage-6 target-machine run is stored in `benchmarks/ollama-gemma4-12b-stage6.json`. With
`gemma4:12b`, three measured runs after warm-up returned every requested entry; batch size 5 had
the best median throughput (124.2 returned entries/minute) and a 4.03-second p95 latency. It is the
default for new or previously unconfigured profiles. Explicitly stored batch sizes are preserved.

The stage-7 CPython JIT, Cython, and Nuitka measurements and the resulting packaging decision are
documented in the [runtime and compiler experiment](performance-stage7.md).

## Model settings inheritance

`ApplicationSettings.model_settings` is the user-scoped global profile. It contains the
translation model, optional reviewer model, reasoning modes, timeout, batch size, Ollama keep-alive,
and system prompts. It is stored in Qt application settings and supplied to `ProjectWorkspace` at
startup. The safe diagnostic report contains only aggregate Ollama timings and token counts; model
inputs, outputs, prompts, and project content are never included.

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
