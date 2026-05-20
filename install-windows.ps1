#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Install the parental-controls agent as a Windows scheduled task.
.DESCRIPTION
    - Installs Python 3.13 system-wide via winget (if not already present)
    - Installs the parental-controls-agent package
    - Creates C:\ProgramData\ParentalControls\agent.toml (prompts for values)
    - Registers a "ParentalControlsAgent" scheduled task that runs at startup
      under the SYSTEM account with automatic restart on failure
.EXAMPLE
    .\install-windows.ps1
#>

# Do NOT use $ErrorActionPreference = "Stop" -- pip writes to stderr and PS 5.1
# turns that into a terminating error, aborting the script before the prompts.

$ConfigDir  = "C:\ProgramData\ParentalControls"
$ConfigFile = "$ConfigDir\agent.toml"
$LogFile    = "$ConfigDir\agent.log"
$TaskName   = "ParentalControlsAgent"

function Write-Step { param([string]$msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$msg) Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Warn { param([string]$msg) Write-Host "    WARN: $msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$msg) Write-Host "    FAIL: $msg" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
# 1. Find or install Python (system-wide so SYSTEM account can run it)
# ---------------------------------------------------------------------------
Write-Step "Checking for Python..."

$pythonExe = $null
foreach ($candidate in @(
    "C:\Program Files\Python313\python.exe",
    "C:\Program Files\Python312\python.exe",
    "C:\Program Files\Python311\python.exe"
)) {
    if (Test-Path $candidate) { $pythonExe = $candidate; break }
}

if (-not $pythonExe) {
    Write-Warn "Python not found in Program Files. Installing via winget..."
    winget install --id Python.Python.3.13 --scope machine --silent `
        --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "winget install failed (exit $LASTEXITCODE). Install Python 3.13 manually from https://python.org, then re-run."
    }

    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")

    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $pythonExe = $cmd.Source }
    if (-not $pythonExe) { $pythonExe = "C:\Program Files\Python313\python.exe" }

    if (-not (Test-Path $pythonExe)) {
        Write-Fail "Python installed but not found at expected path. Re-run this script."
    }
}

Write-OK "Python: $pythonExe"
& $pythonExe --version

# ---------------------------------------------------------------------------
# 2. Install the package
# ---------------------------------------------------------------------------
Write-Step "Installing parental-controls-agent..."

Push-Location $PSScriptRoot
& $pythonExe -m pip install --quiet "." 2>$null
& $pythonExe -m pip install --quiet httpx 2>$null
Pop-Location

& $pythonExe -c "import parental_controls_agent" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Package import failed. Check that the repo is intact and re-run."
}
Write-OK "Package installed."

# ---------------------------------------------------------------------------
# 3. Config file
# ---------------------------------------------------------------------------
Write-Step "Setting up $ConfigFile ..."

if (-not (Test-Path $ConfigDir)) {
    New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
}

if (Test-Path $ConfigFile) {
    Write-OK "Config already exists - skipping. Delete it to re-run setup:"
    Write-Host "    Remove-Item '$ConfigFile'"
} else {
    Write-Host ""
    $serverUrl = Read-Host "  Server URL [https://parental-controls.graysonhead.net]"
    if ([string]::IsNullOrWhiteSpace($serverUrl)) {
        $serverUrl = "https://parental-controls.graysonhead.net"
    }
    $serverUrl = $serverUrl.TrimEnd("/")

    Write-Host ""
    Write-Host "  Enter each child's web-UI display name and Windows username." -ForegroundColor White
    Write-Host "  Leave the display name blank when done." -ForegroundColor Gray
    Write-Host ""

    $childrenLines = @()
    while ($true) {
        $webName = Read-Host "  Child display name (blank to finish)"
        if ([string]::IsNullOrWhiteSpace($webName)) { break }
        $winUser = Read-Host "  Windows username for '$webName'"
        $childrenLines += "`"$webName`" = `"$winUser`""
    }

    $tomlLines = @(
        "server_url = `"$serverUrl`"",
        "poll_interval = 30",
        "",
        "[children]"
    ) + $childrenLines

    # Use .NET directly — PS 5.1's "utf8" encoding writes a BOM which breaks tomllib
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($ConfigFile, ($tomlLines -join "`n"), $utf8NoBom)
    Write-OK "Config written."
    Get-Content $ConfigFile | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
}

# ---------------------------------------------------------------------------
# 4. Scheduled task (registered via XML to avoid quoting issues with spaces in paths)
# ---------------------------------------------------------------------------
Write-Step "Registering scheduled task '$TaskName' ..."

schtasks /delete /tn $TaskName /f 2>$null

# S-1-5-18 = SYSTEM account; PT0S = no execution time limit
$taskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <BootTrigger><Enabled>true</Enabled></BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure>
      <Interval>PT2M</Interval>
      <Count>5</Count>
    </RestartOnFailure>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$pythonExe</Command>
      <Arguments>-m parental_controls_agent -c "$ConfigFile"</Arguments>
      <WorkingDirectory>$ConfigDir</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

$xmlPath = "$env:TEMP\parental-controls-task.xml"
# schtasks requires the XML file to be UTF-16 LE
[System.IO.File]::WriteAllText($xmlPath, $taskXml, [System.Text.Encoding]::Unicode)

schtasks /create /tn $TaskName /xml $xmlPath /f
if ($LASTEXITCODE -ne 0) {
    Write-Fail "schtasks /create failed (exit $LASTEXITCODE)."
}
Write-OK "Task registered."

# ---------------------------------------------------------------------------
# 5. Start now
# ---------------------------------------------------------------------------
Write-Step "Starting agent now..."
schtasks /run /tn $TaskName
if ($LASTEXITCODE -ne 0) {
    Write-Warn "schtasks /run failed - agent will still start on next reboot."
}
Start-Sleep -Seconds 5

$logContent = Get-Content $LogFile -Tail 5 -ErrorAction SilentlyContinue
if ($logContent) {
    Write-OK "Agent is logging:"
    $logContent | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
} else {
    Write-Warn "Log file empty after 5s. Check $LogFile after a moment."
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Done!" -ForegroundColor Green
Write-Host "  Config : $ConfigFile"
Write-Host "  Logs   : $LogFile"
Write-Host "  Task   : $TaskName  (SYSTEM, runs at every boot)"
Write-Host ""
Write-Host "To uninstall (run as admin):"
Write-Host "  schtasks /delete /tn $TaskName /f"
Write-Host ""
