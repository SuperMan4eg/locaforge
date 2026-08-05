# Development

## Local setup

Use Python 3.12 or newer.

```powershell
python -m pip install -e ".[dev]"
$env:PYTHONPATH = "src"
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest
python -m ruff check src tests
python -m mypy src
```

Run the desktop application after installation with:

```powershell
locaforge
```

## Windows portable build

Install the build dependency and create a self-contained Windows x64 bundle:

```powershell
python -m pip install -e ".[build]"
.\scripts\build_windows.ps1
```

The script creates `dist/LocaForge/LocaForge.exe` and the portable archive
`dist/LocaForge-0.1.0-windows-x64.zip`. End users do not need Python installed.
Ollama remains a separate installation for local AI translation.

## Continuous integration

GitHub Actions runs the test suite, Ruff and mypy on Python 3.12 and 3.13. A separate job builds the source and wheel distributions to verify packaging metadata.
