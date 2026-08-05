param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DistDirectory = Join-Path $ProjectRoot "dist"
$BundleDirectory = Join-Path $DistDirectory "LocaForge"
$ArchivePath = Join-Path $DistDirectory "LocaForge-0.1.0-windows-x64.zip"

Push-Location $ProjectRoot
try {
    & $Python -m PyInstaller --clean --noconfirm packaging/locaforge.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
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
