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
    [string]$Project = "7b165071-f006-4c3a-8707-1260983cee58",
    [int]$CheckSeconds = 30,
    [int]$RailwayTimeoutSeconds = 90,
    [int]$HeartbeatSeconds = 600,
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

$railwayCmd = (Get-Command railway.cmd -ErrorAction SilentlyContinue | Select-Object -First 1).Source
$nodeExe = (Get-Command node.exe -ErrorAction SilentlyContinue | Select-Object -First 1).Source
$railwayJs = $null
if ($railwayCmd) {
    $railwayJs = Join-Path (Split-Path $railwayCmd) "node_modules\@railway\cli\bin\railway.js"
}

$mutex = New-Object System.Threading.Mutex($false, "Global\ORQEVA-Bridge-Stack")
if (-not $mutex.WaitOne(0)) {
    Write-Host "another bridge watchdog is already running"
    exit 0
}

$script:lastHeartbeat = [datetime]::MinValue

function Log([string]$message) {
    $line = "$(Get-Date -Format o) $message"
    Write-Host $line
    Add-Content -Path $watchLog -Value $line -Encoding UTF8
}

function Write-Heartbeat([string]$status) {
    if (((Get-Date) - $script:lastHeartbeat).TotalSeconds -lt $HeartbeatSeconds) { return }
    $script:lastHeartbeat = Get-Date
    Log "heartbeat $status"
}

function Invoke-Railway {
    param(
        [string[]]$Arguments,
        [int]$TimeoutSeconds = $RailwayTimeoutSeconds
    )
    if (-not $nodeExe -or -not $railwayJs -or -not (Test-Path $railwayJs)) {
        return [pscustomobject]@{ ExitCode = -1; StdOut = ""; StdErr = "node or railway.js not found"; TimedOut = $false }
    }
    $quoted = $Arguments | ForEach-Object {
        if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
    }
    $argLine = '"' + $railwayJs + '" ' + (@($quoted) -join ' ')
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $nodeExe
    $psi.Arguments = $argLine
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    try {
        [void]$p.Start()
        $stdoutTask = $p.StandardOutput.ReadToEndAsync()
        $stderrTask = $p.StandardError.ReadToEndAsync()
        if (-not $p.WaitForExit($TimeoutSeconds * 1000)) {
            & taskkill.exe /PID $p.Id /T /F 2>&1 | Out-Null
            return [pscustomobject]@{ ExitCode = -1; StdOut = ""; StdErr = "timed out after ${TimeoutSeconds}s"; TimedOut = $true }
        }
        $p.WaitForExit()
        $stdout = [string]$stdoutTask.Result
        $stderr = [string]$stderrTask.Result
        return [pscustomobject]@{ ExitCode = $p.ExitCode; StdOut = $stdout; StdErr = $stderr; TimedOut = $false }
    } catch {
        return [pscustomobject]@{ ExitCode = -1; StdOut = ""; StdErr = $_.Exception.Message; TimedOut = $false }
    } finally {
        $p.Dispose()
    }
}

function Test-Bridge {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:8100/health" -TimeoutSec 5
        return [bool]($r.status -eq "ok")
    } catch {
        return $false
    }
}

function Test-TunnelHealth([string]$url) {
    if (-not $url) { return $false }
    try {
        $r = Invoke-RestMethod -Uri "$url/health" -TimeoutSec 15
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
    $lines = Get-Content -Path $cfErr -Tail 200 -ErrorAction SilentlyContinue
    if (-not $lines) { return $null }
    $matches = $lines | Select-String -Pattern "https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com" -AllMatches
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
        -ArgumentList @("tunnel", "--no-autoupdate", "--protocol", "http2",
                        "--edge-ip-version", "4", "--url", "http://127.0.0.1:8100") `
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
    $res = Invoke-Railway @("variables", "--service", $Service, "--environment", $Environment,
                            "--project", $Project, "--json") 60
    if ($res.ExitCode -ne 0) {
        $detail = ([string]$res.StdErr).Trim()
        if (-not $detail) { $detail = ([string]$res.StdOut).Trim() }
        Log "Railway read failed (exit=$($res.ExitCode)): $detail"
        return $null
    }
    try {
        return (([string]$res.StdOut) | ConvertFrom-Json).EXNESS_BRIDGE_URL
    } catch {
        Log "Railway read parse failed"
        return $null
    }
}

function Sync-Railway([string]$url) {
    if ($NoRailway -or -not $url) { return $false }
    $state = $null
    if (Test-Path $statePath) {
        try { $state = Get-Content $statePath -Raw | ConvertFrom-Json } catch { $state = $null }
    }
    if ($state -and $state.last_url -eq $url -and $state.redeployed_at) {
        $age = (Get-Date) - [datetime]$state.redeployed_at
        if ($age.TotalMinutes -lt 10) { return $true }
    }
    $current = Get-RailwayUrl
    if (-not $current) { return $false }
    $needsRedeploy = ($state -eq $null) -or ($state.last_url -ne $url) -or (-not $state.redeployed_at)
    if ($current -eq $url -and -not $needsRedeploy) {
        @{ last_url = $url; synced_at = (Get-Date).ToString("o"); redeployed_at = $state.redeployed_at } |
            ConvertTo-Json | Set-Content $statePath
        return $true
    }
    if ($current -ne $url) {
        Log "updating Railway EXNESS_BRIDGE_URL"
        $set = Invoke-Railway @("variable", "set", "EXNESS_BRIDGE_URL=$url", "--service", $Service,
                                "--environment", $Environment, "--project", $Project, "--skip-deploys") $RailwayTimeoutSeconds
        if ($set.ExitCode -ne 0) {
            $detail = ([string]$set.StdErr).Trim()
            if (-not $detail) { $detail = ([string]$set.StdOut).Trim() }
            Log "Railway variable update failed (exit=$($set.ExitCode)): $detail"
            return $false
        }
        $needsRedeploy = $true
    }
    if ($needsRedeploy) {
        Log "redeploying Railway backend"
        $dep = Invoke-Railway @("redeploy", "--service", $Service, "--environment", $Environment,
                                "--project", $Project, "--yes") 180
        if ($dep.ExitCode -ne 0) {
            $detail = ([string]$dep.StdErr).Trim()
            if (-not $detail) { $detail = ([string]$dep.StdOut).Trim() }
            Log "Railway redeploy failed (exit=$($dep.ExitCode)): $detail"
            return $false
        }
        $now = (Get-Date).ToString("o")
        @{ last_url = $url; synced_at = $now; redeployed_at = $now } |
            ConvertTo-Json | Set-Content $statePath
        Log "Railway updated to $url"
    }
    return $true
}

try {
    Log "watchdog starting (repo=$RepoRoot service=$Service project=$Project)"
    Start-Mt5
    $bridgeOk = Start-Bridge
    $url = Start-Tunnel
    [void](Sync-Railway $url)
    Write-Heartbeat "bridge=$bridgeOk tunnel=$url"

    if ($Once) { Log "single pass complete"; exit 0 }

    $tunnelFailures = 0
    while ($true) {
        Start-Sleep -Seconds $CheckSeconds
        $bridgeOk = Test-Bridge
        if (-not $bridgeOk) {
            Log "bridge health check failed"
            $bridgeOk = Start-Bridge
        }
        if (-not (Get-Process cloudflared -ErrorAction SilentlyContinue)) {
            Log "cloudflared is not running"
            $url = Start-Tunnel
            $tunnelFailures = 0
        } else {
            $url = Get-TunnelUrl
            if (-not $url -or -not (Test-TunnelHealth $url)) {
                $tunnelFailures++
                Log "tunnel health check failed ($tunnelFailures): $url"
                if ($tunnelFailures -ge 2) {
                    Log "restarting cloudflared"
                    Stop-Process -Name cloudflared -Force -ErrorAction SilentlyContinue
                    Start-Sleep -Seconds 2
                    $url = Start-Tunnel
                    $tunnelFailures = 0
                }
            } else {
                $tunnelFailures = 0
            }
        }
        if ($url) { [void](Sync-Railway $url) }
        Write-Heartbeat "bridge=$bridgeOk tunnel=$url"
    }
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
