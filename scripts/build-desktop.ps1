[CmdletBinding()]
param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$venv = Join-Path $root ".desktop-build"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $pythonCandidates = @()
    if ($env:ALLOLABS_BUILD_PYTHON) {
        $pythonCandidates += $env:ALLOLABS_BUILD_PYTHON
    }
    foreach ($commandName in @("python", "python3")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command) {
            $pythonCandidates += $command.Source
        }
    }
    foreach ($version in @("314", "313", "312", "311")) {
        $pythonCandidates += Join-Path $env:LOCALAPPDATA "Programs\Python\Python$version\python.exe"
    }

    $bootstrapPython = $pythonCandidates |
        Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
        Select-Object -First 1
    if (-not $bootstrapPython) {
        throw "Python 3.11 or newer was not found. Set ALLOLABS_BUILD_PYTHON to python.exe."
    }
    & $bootstrapPython -m venv $venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "Could not create the desktop build environment with $bootstrapPython."
    }
}

& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Could not update pip in the desktop build environment."
}
& $python -m pip install -r (Join-Path $root "requirements-desktop.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Could not install the AlloLabs desktop build requirements."
}
& $python -m PyInstaller --noconfirm --clean (Join-Path $root "packaging\allolabs.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller could not build the AlloLabs desktop application."
}
& powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File (Join-Path $root "scripts\verify-portable.ps1") `
    -PortablePath (Join-Path $root "dist\AlloLabs")
if ($LASTEXITCODE -ne 0) {
    throw "The AlloLabs portable verification failed."
}
$portableSource = Join-Path $root "dist\AlloLabs"
$portableTarget = Join-Path $root "dist\AlloLabs-Windows-x64"
if (Test-Path -LiteralPath $portableTarget) {
    Remove-Item -LiteralPath $portableTarget -Recurse -Force
}
Move-Item -LiteralPath $portableSource -Destination $portableTarget

if (-not $SkipInstaller) {
    $iscc = @(
        (Get-Command iscc.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1

    if (-not $iscc) {
        throw "Inno Setup 6 was not found. Install it or rerun with -SkipInstaller."
    }
    & $iscc (Join-Path $root "packaging\allolabs.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup could not build the AlloLabs installer."
    }
}

Write-Host "AlloLabs desktop build complete." -ForegroundColor Green
