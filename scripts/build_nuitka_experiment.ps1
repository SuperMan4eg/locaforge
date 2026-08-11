param(
    [string]$Python = ".\.venv\Scripts\python.exe",
    [string]$OutputDirectory = "build\stage7-nuitka"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ResolvedOutput = Join-Path $ProjectRoot $OutputDirectory

Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = "src"
    & $Python -m nuitka `
        --mode=standalone `
        --assume-yes-for-downloads `
        --enable-plugin=pyside6 `
        --msvc=latest `
        --windows-console-mode=disable `
        --output-dir=$ResolvedOutput `
        --output-filename=LocaForge-Nuitka.exe `
        --include-data-dir=src/locaforge/resources/locales=locaforge/resources/locales `
        --nofollow-import-to=pytest `
        --nofollow-import-to=mypy `
        --nofollow-import-to=ruff `
        --python-flag=-m `
        src/locaforge
    if ($LASTEXITCODE -ne 0) {
        throw "Nuitka failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
