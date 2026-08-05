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

## Continuous integration

GitHub Actions runs the test suite, Ruff and mypy on Python 3.12 and 3.13. A separate job builds the source and wheel distributions to verify packaging metadata.
