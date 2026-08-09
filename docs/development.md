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

The script reads the version from `pyproject.toml` and creates
`dist/LocaForge/LocaForge.exe` plus
`dist/LocaForge-<version>-windows-x64.zip`. End users do not need Python installed.
Ollama remains a separate installation for local AI translation.

Smoke-test the packaged executable without leaving the GUI open:

```powershell
$process = Start-Process -FilePath ".\dist\LocaForge\LocaForge.exe" `
    -ArgumentList "--smoke-test" -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Smoke test failed" }
```

## Continuous integration

GitHub Actions runs the test suite, Ruff and mypy on Python 3.12 and 3.13. Separate
jobs build the Python distributions and the Windows portable archive. The Windows
job starts the packaged executable in smoke-test mode on every push and pull request.

## Release process

1. Update `pyproject.toml`, `README.md`, and `CHANGELOG.md` for the release.
2. Merge the release changes into `main` and ensure CI is green.
3. Create and push an annotated tag matching the package version, for example
   `v0.3.0`.
4. CI verifies the tag/version match, downloads the build artifacts, creates
   `SHA256SUMS.txt`, and publishes the GitHub Release.

The release contains the wheel, source distribution, Windows portable ZIP, and
checksums. A tag that does not match the version in `pyproject.toml` fails before
publishing.
