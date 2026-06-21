[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$PortablePath
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $PortablePath) {
    $PortablePath = Join-Path $root "dist\AlloLabs"
}
$portable = [System.IO.Path]::GetFullPath($PortablePath)

$required = @(
    "AlloLabs.exe",
    "AlloLabsWorker.exe",
    "_internal\allolabs.py",
    "_internal\dashboard\index.html",
    "_internal\dashboard\app.js",
    "_internal\resources\allolabs-logo.png",
    "_internal\resources\company-logos\manifest.json",
    "_internal\examples\default-run.json",
    "_internal\examples\default-portfolio-report.pdf",
    "_internal\python311.dll",
    "_internal\VCRUNTIME140.dll"
)

$missing = @(
    $required | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $portable $_) -PathType Leaf)
    }
)
if ($missing.Count -gt 0) {
    throw "Portable build is incomplete. Missing: $($missing -join ', ')"
}

$worker = Join-Path $portable "AlloLabsWorker.exe"
$output = & $worker --self-test
if ($LASTEXITCODE -ne 0) {
    throw "AlloLabsWorker self-test failed with exit code $LASTEXITCODE."
}
$result = $output | ConvertFrom-Json
if ($result.status -ne "ok" -or $result.apiVersion -lt 19) {
    throw "AlloLabsWorker returned an invalid self-test result."
}

$files = Get-ChildItem -LiteralPath $portable -Recurse -File
$size = [math]::Round((($files | Measure-Object Length -Sum).Sum / 1MB), 2)
Write-Host "AlloLabs portable build verified." -ForegroundColor Green
Write-Host "Files: $($files.Count) | Size: $size MB | Python: $($result.python)"
