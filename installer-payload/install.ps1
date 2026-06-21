$ErrorActionPreference = "Stop"
$version = "1.3.1"
$appName = "AlloLabs"
$sourceZip = Join-Path $PSScriptRoot "AlloLabs-v1.3.1-Windows-x64.zip"
$installRoot = Join-Path $env:LOCALAPPDATA "Programs\AlloLabs"
$tempTarget = "$installRoot.new"
$oldTarget = "$installRoot.old"

if (-not (Test-Path -LiteralPath $sourceZip -PathType Leaf)) {
    throw "Installer payload is missing: $sourceZip"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $installRoot) | Out-Null
if (Test-Path -LiteralPath $tempTarget) { Remove-Item -LiteralPath $tempTarget -Recurse -Force }
New-Item -ItemType Directory -Force -Path $tempTarget | Out-Null
Expand-Archive -LiteralPath $sourceZip -DestinationPath $tempTarget -Force

$exe = Join-Path $tempTarget "AlloLabs.exe"
$worker = Join-Path $tempTarget "AlloLabsWorker.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf) -or -not (Test-Path -LiteralPath $worker -PathType Leaf)) {
    throw "Extracted app is incomplete. AlloLabs.exe or AlloLabsWorker.exe was not found."
}

Get-Process AlloLabs,AlloLabsWorker -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
if (Test-Path -LiteralPath $oldTarget) { Remove-Item -LiteralPath $oldTarget -Recurse -Force }
if (Test-Path -LiteralPath $installRoot) { Rename-Item -LiteralPath $installRoot -NewName (Split-Path -Leaf $oldTarget) -Force }
Rename-Item -LiteralPath $tempTarget -NewName (Split-Path -Leaf $installRoot) -Force
if (Test-Path -LiteralPath $oldTarget) { Remove-Item -LiteralPath $oldTarget -Recurse -Force }

$wsh = New-Object -ComObject WScript.Shell
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\AlloLabs"
New-Item -ItemType Directory -Force -Path $startMenuDir | Out-Null
$shortcuts = @(
    Join-Path $startMenuDir "AlloLabs.lnk",
    Join-Path ([Environment]::GetFolderPath("Desktop")) "AlloLabs.lnk"
)
foreach ($shortcutPath in $shortcuts) {
    $shortcut = $wsh.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $installRoot "AlloLabs.exe"
    $shortcut.WorkingDirectory = $installRoot
    $shortcut.IconLocation = Join-Path $installRoot "AlloLabs.exe"
    $shortcut.Description = "AlloLabs v$version"
    $shortcut.Save()
}

$uninstall = @"
`$ErrorActionPreference = "Stop"
Get-Process AlloLabs,AlloLabsWorker -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$installRoot" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$startMenuDir" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$(Join-Path ([Environment]::GetFolderPath("Desktop")) "AlloLabs.lnk")" -Force -ErrorAction SilentlyContinue
"@
Set-Content -LiteralPath (Join-Path $installRoot "Uninstall-AlloLabs.ps1") -Value $uninstall -Encoding UTF8

Write-Host "AlloLabs v$version installed to $installRoot"
Start-Process -FilePath (Join-Path $installRoot "AlloLabs.exe")
