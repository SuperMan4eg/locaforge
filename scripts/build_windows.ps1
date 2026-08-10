param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DistDirectory = Join-Path $ProjectRoot "dist"
$BundleDirectory = Join-Path $DistDirectory "LocaForge"

Push-Location $ProjectRoot
try {
    $Version = & $Python -c "import pathlib, tomllib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])"
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Version)) {
        throw "Cannot read the project version from pyproject.toml"
    }
    $ArchivePath = Join-Path $DistDirectory "LocaForge-$Version-windows-x64.zip"

    & $Python -m PyInstaller --clean --noconfirm packaging/locaforge.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }

    foreach ($Locale in @("en.json", "ru.json")) {
        $LocalePath = Join-Path $BundleDirectory "_internal\locaforge\resources\locales\$Locale"
        if (-not (Test-Path -LiteralPath $LocalePath -PathType Leaf)) {
            throw "Portable bundle is missing localization: $Locale"
        }
    }

    if (Test-Path -LiteralPath $ArchivePath) {
        Remove-Item -LiteralPath $ArchivePath
    }
    Compress-Archive -Path (Join-Path $BundleDirectory "*") -DestinationPath $ArchivePath
    Write-Host "Windows bundle: $BundleDirectory"
    Write-Host "Portable archive: $ArchivePath"
}
finally {
    Pop-Location
}
