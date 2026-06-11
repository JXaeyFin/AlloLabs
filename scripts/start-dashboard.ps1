[CmdletBinding()]
param(
    [switch]$Restart
)

$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$serverPath = Join-Path $repositoryRoot "dashboard\server.py"
$requiredModules = "matplotlib,numpy,pandas,scipy,yfinance"
$port = 8765

if (-not (Test-Path -LiteralPath $serverPath -PathType Leaf)) {
    throw "Dashboard server not found: $serverPath"
}

$candidates = @()
if ($env:WEALTHGPT_ANALYSIS_PYTHON) {
    $candidates += [pscustomobject]@{
        Executable = $env:WEALTHGPT_ANALYSIS_PYTHON
        Arguments = @()
    }
}

foreach ($commandName in @("python", "python3")) {
    $command = Get-Command $commandName -ErrorAction SilentlyContinue
    if ($command) {
        $candidates += [pscustomobject]@{
            Executable = $command.Source
            Arguments = @()
        }
    }
}

$pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
if ($pyLauncher) {
    $candidates += [pscustomobject]@{
        Executable = $pyLauncher.Source
        Arguments = @("-3")
    }
}

$selected = $null
foreach ($candidate in $candidates) {
    try {
        $probe = "import $($requiredModules -replace ',', '; import ')"
        & $candidate.Executable @($candidate.Arguments) -c $probe 2>$null
        if ($LASTEXITCODE -eq 0) {
            $selected = $candidate
            break
        }
    } catch {
        continue
    }
}

if (-not $selected) {
    throw "No Python installation with the WealthGPT requirements was found. Run: python -m pip install -r requirements.txt"
}

$listeners = @(
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
)

if ($listeners.Count -gt 0 -and -not $Restart) {
    $url = "http://127.0.0.1:$port/"
    Write-Host "WealthGPT is already running at $url"
    Start-Process $url
    exit 0
}

if ($Restart) {
    foreach ($processId in $listeners) {
        if ($processId -and $processId -ne $PID) {
            Write-Host "Stopping existing dashboard process $processId..."
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }

    $deadline = (Get-Date).AddSeconds(8)
    do {
        Start-Sleep -Milliseconds 200
        $remaining = @(
            Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        )
    } while ($remaining.Count -gt 0 -and (Get-Date) -lt $deadline)

    if ($remaining.Count -gt 0) {
        throw "Port $port is still in use after the restart request."
    }
}

$url = "http://127.0.0.1:$port/"
Write-Host "Starting WealthGPT at $url"
Start-Process $url
& $selected.Executable @($selected.Arguments) $serverPath --port $port
exit $LASTEXITCODE
