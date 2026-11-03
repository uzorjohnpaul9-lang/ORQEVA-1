<#
.SYNOPSIS
  Keep the Exness MT5 bridge and its Cloudflare quick tunnel alive, and keep
  Railway's EXNESS_BRIDGE_URL pointed at the current tunnel.

.DESCRIPTION
  Quick tunnels mint a new https://<random>.trycloudflare.com hostname every
  time cloudflared starts. This watchdog:
    * starts MT5 / the uvicorn bridge / cloudflared when they are missing,
    * reads the current tunnel URL from the cloudflared log,
    * updates Railway and redeploys only when the URL actually changed,
    * writes heartbeat logs under logs/.

  Run it from a Scheduled Task at logon (see install-bridge-task.ps1). It is
  idempotent: if the bridge and tunnel are already up it just monitors them.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$Service = "ORQEVA-1",
    [string]$Environment = "production",
    [int]$CheckSeconds = 30,
    [switch]$NoRailway,
    [switch]$Once
)

$ErrorActionPreference = "Continue"
if (-not $RepoRoot) {
    $base = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
    $RepoRoot = (Resolve-Path (Join-Path $base "..")).Path
}
$logs = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$watchLog = Join-Path $logs "bridge-watchdog.log"
$statePath = Join-Path $logs "bridge-stack.json"
$cfOut = Join-Path $logs "cloudflared.out.log"
$cfErr = Join-Path $logs "cloudflared.err.log"
$cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$mt5Path = "C:\Program Files\MetaTrader 5\terminal64.exe"

$mutex = New-Object System.Threading.Mutex($false, "Global\ORQEVA-Bridge-Stack")
if (-not $mutex.WaitOne(0)) {
    Write-Host "another bridge watchdog is already running"
    exit 0
}

function Log([string]$message) {
    $line = "$(Get-Date -Format o) $message"
    Write-Host $line
    Add-Content -Path $watchLog -Value $line -Encoding UTF8
}

function Test-Bridge {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:8100/health" -TimeoutSec 5
        return [bool]($r.status -eq "ok")
    } catch {
        return $false
    }
}

function Start-Mt5 {
    if (Get-Process terminal64 -ErrorAction SilentlyContinue) { return }
    if (-not (Test-Path $mt5Path)) { Log "MT5 not installed at $mt5Path"; return }
    Log "starting MT5 terminal"
    Start-Process -FilePath $mt5Path | Out-Null
    Start-Sleep -Seconds 10
}

function Start-Bridge {
    if (Test-Bridge) { return $true }
    $stale = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'bridge\.mt5_bridge' }
    foreach ($p in $stale) {
        Log "stopping unresponsive bridge process $($p.ProcessId)"
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Log "starting bridge"
    Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "`"$RepoRoot\bridge\run_bridge.bat`"" `
        -WorkingDirectory $RepoRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logs "bridge.out.log") `
        -RedirectStandardError (Join-Path $logs "bridge.err.log") | Out-Null
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Bridge) { Log "bridge healthy"; return $true }
    }
    Log "bridge did not become healthy"
    return $false
}

function Get-TunnelUrl {
    if (-not (Test-Path $cfErr)) { return $null }
    $matches = Select-String -Path $cfErr -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -AllMatches
    if (-not $matches) { return $null }
    $all = @($matches | ForEach-Object { $_.Matches } | ForEach-Object { $_.Value })
    if ($all.Count -eq 0) { return $null }
    return $all[$all.Count - 1]
}

function Start-Tunnel {
    if (Get-Process cloudflared -ErrorAction SilentlyContinue) { return (Get-TunnelUrl) }
    if (-not (Test-Path $cloudflared)) { Log "cloudflared not installed at $cloudflared"; return $null }
    Log "starting cloudflared quick tunnel"
    Remove-Item $cfErr, $cfOut -ErrorAction SilentlyContinue
    Start-Process -FilePath $cloudflared `
        -ArgumentList "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:8100" `
        -WorkingDirectory $RepoRoot -WindowStyle Hidden `
        -RedirectStandardOutput $cfOut -RedirectStandardError $cfErr | Out-Null
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 1
        $url = Get-TunnelUrl
        if ($url) { Log "tunnel url $url"; return $url }
    }
    Log "cloudflared did not print a tunnel URL"
    return $null
}

function Get-RailwayUrl {
    try {
        $json = & railway variables --service $Service --environment $Environment --json 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $json) { return $null }
        return ($json | ConvertFrom-Json).EXNESS_BRIDGE_URL
    } catch {
        return $null
    }
}

function Sync-Railway([string]$url) {
    if ($NoRailway -or -not $url) { return }
    $state = $null
    if (Test-Path $statePath) {
        try { $state = Get-Content $statePath -Raw | ConvertFrom-Json } catch { $state = $null }
    }
    if ($state -and $state.last_url -eq $url) { return }
    if ((Get-RailwayUrl) -eq $url) {
        @{ last_url = $url; synced_at = (Get-Date).ToString("o") } | ConvertTo-Json | Set-Content $statePath
        return
    }
    Log "updating Railway EXNESS_BRIDGE_URL"
    $ok = $false
    for ($i = 0; $i -lt 3 -and -not $ok; $i++) {
        try {
            & railway variables --service $Service --environment $Environment `
                --set "EXNESS_BRIDGE_URL=$url" 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { $ok = $true } else { Start-Sleep -Seconds 5 }
        } catch {
            Start-Sleep -Seconds 5
        }
    }
    if (-not $ok) { Log "Railway variable update failed"; return }
    Log "redeploying Railway backend"
    try { & railway redeploy --service $Service --yes 2>&1 | Out-Null } catch { }
    @{ last_url = $url; synced_at = (Get-Date).ToString("o") } | ConvertTo-Json | Set-Content $statePath
    Log "Railway updated to $url"
}

try {
    Log "watchdog starting (repo=$RepoRoot service=$Service)"
    Start-Mt5
    [void](Start-Bridge)
    $url = Start-Tunnel
    Sync-Railway $url

    if ($Once) { Log "single pass complete"; exit 0 }

    while ($true) {
        Start-Sleep -Seconds $CheckSeconds
        if (-not (Get-Process terminal64 -ErrorAction SilentlyContinue)) {
            Start-Mt5
        }
        if (-not (Test-Bridge)) {
            Log "bridge health check failed"
            [void](Start-Bridge)
        }
        if (-not (Get-Process cloudflared -ErrorAction SilentlyContinue)) {
            Log "cloudflared is not running"
            $url = Start-Tunnel
            Sync-Railway $url
        } else {
            $url = Get-TunnelUrl
            if ($url) { Sync-Railway $url }
        }
    }
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
