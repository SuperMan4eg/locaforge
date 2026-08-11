param(
    [string]$Python = ".\.venv\Scripts\python.exe",
    [string]$OutputDirectory = "build\stage7-nuitka-benchmark"
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
        --windows-console-mode=force `
        --output-dir=$ResolvedOutput `
        --output-filename=LocaForge-Benchmark-Nuitka.exe `
        --include-package=locaforge `
        --nofollow-import-to=pytest `
        --nofollow-import-to=mypy `
        --nofollow-import-to=ruff `
        scripts/benchmark_performance.py
    if ($LASTEXITCODE -ne 0) {
        throw "Nuitka benchmark build failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
