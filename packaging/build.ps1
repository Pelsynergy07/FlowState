# Builds FlowState end-to-end: PyInstaller (onedir) -> Inno Setup installer.
# Run from anywhere; paths are resolved relative to this script, not the
# caller's current directory or any dev-machine-specific location.

$ErrorActionPreference = "Stop"

$PackagingDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $PackagingDir
$Venv = Join-Path $ProjectRoot ".venv\Scripts"

Write-Host "== 1/2: PyInstaller (onedir) ==" -ForegroundColor Cyan
& "$Venv\python.exe" -m PyInstaller "$PackagingDir\flowstate.spec" `
    --distpath "$PackagingDir\dist" `
    --workpath "$PackagingDir\build" `
    --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

Write-Host "== 2/2: Inno Setup installer ==" -ForegroundColor Cyan
$ISCC = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $ISCC)) {
    $ISCC = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path $ISCC)) {
    throw "Could not find ISCC.exe (Inno Setup compiler). Install Inno Setup 6 first."
}

& $ISCC "$PackagingDir\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed" }

$OutputExe = Join-Path $PackagingDir "dist_installer\FlowStateSetup.exe"
Write-Host ""
Write-Host "Done. Installer at: $OutputExe" -ForegroundColor Green
