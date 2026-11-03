<#
.SYNOPSIS
  Register the ORQEVA bridge watchdog as a per-user Scheduled Task at logon.

.DESCRIPTION
  The watchdog needs the user's MT5 terminal session and the user-level
  MT5_BRIDGE_TOKEN / Railway CLI login, so it runs interactively at logon
  rather than as a service.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$TaskName = "ORQEVA Bridge Stack",
    [switch]$StartNow
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
    $base = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
    $RepoRoot = (Resolve-Path (Join-Path $base "..")).Path
}
$script = Join-Path $RepoRoot "deploy\bridge-stack.ps1"
if (-not (Test-Path $script)) { throw "watchdog not found: $script" }

$powershell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""

$action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 3650)

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Keeps the Exness MT5 bridge + Cloudflare tunnel alive and syncs the URL to Railway." `
        -Force | Out-Null
    Write-Host "registered scheduled task: $TaskName"
    if ($StartNow) {
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "started scheduled task: $TaskName"
    }
} catch {
    Write-Warning "Scheduled Task creation was denied: $($_.Exception.Message)"
    Write-Warning "Falling back to the current user's Startup folder (no admin required)."
    $startup = [Environment]::GetFolderPath("Startup")
    $launcher = Join-Path $startup "ORQEVA Bridge.vbs"
    $vbsCmd = ("`"$powershell`" $arguments").Replace('"', '""')
    $vbs = @"
Set sh = CreateObject("WScript.Shell")
sh.Run "$vbsCmd", 0, False
"@
    Set-Content -Path $launcher -Value $vbs -Encoding ASCII
    Write-Host "installed startup launcher: $launcher"
    if ($StartNow) {
        Start-Process -FilePath "wscript.exe" -ArgumentList "`"$launcher`""
        Write-Host "started startup launcher"
    }
}
