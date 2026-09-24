# ============================================================================
# WINDOWS VPS DEPLOYMENT GUIDE - ORQEVA backend (FastAPI, native, no Docker)
# ============================================================================
# The frontend is static on Cloudflare Pages (orqeva.pages.dev). Only the
# Python API runs on the VPS. This is the Windows-native path: same tools you
# already run locally (git + Python + uvicorn), no WSL/Docker needed.
#
# Assumes: Windows Server 2019/2022 or Windows 10/11 VPS, Python 3.11 installed
# and on PATH, and an admin PowerShell session for the setup steps.
# ============================================================================

## STEP 1 - Install Git (if missing) and clone the repo
# From Microsoft Store or https://git-scm.com/download/win . Then:
#   cd C:\
#   git clone https://github.com/uzorjohnpaul9-lang/ORQEVA-1.git orqeva
#   cd C:\orqeva

## STEP 2 - Create the backend .env (paste your REAL keys)
# Substitutions from your local C:\Users\Munachi\ai-trading-system\.env
# (same values). Generate FRESH SECRET_KEY + ENCRYPTION_KEY on the VPS:
#   SECRET_KEY:    python -c "import secrets;print(secrets.token_hex(32))"
#   ENCRYPTION_KEY: python -c "import base64,secrets;print(base64.b64encode(secrets.token_bytes(32)).decode())"
# Asset env key: no.

Set-Content -Path C:\orqeva\.env -Value @'
SUPABASE_URL=https://crysjnakhwveokjrydyw.supabase.co
SUPABASE_PUBLISHABLE_KEY=********PASTE_ME********
SUPABASE_SECRET_KEY=********PASTE_ME********
SECRET_KEY=********PASTE_ME********
ENCRYPTION_KEY=********PASTE_ME********
ADMIN_EMAIL=uzorjohnpaul9@gmail.com
ADMIN_PASSWORD=********PASTE_ME********
ALPACA_API_KEY=********PASTE_ME********
ALPACA_SECRET_KEY=********PASTE_ME********
ALPACA_BASE_URL=https://paper-api.alpaca.markets
TWELVE_DATA_API_KEY=********PASTE_ME********
SCAN_ENABLED=1
SCAN_INTERVAL_MINUTES=60
SCAN_COOLDOWN_HOURS=4
TRADING_ENABLED=false
CORS_ORIGINS=["https://orqeva.pages.dev"]
'@
# Then replace every ********PASTE_ME******** via:
#   notepad C:\orqeva\.env

## STEP 3 - Install dependencies
cd C:\orqeva
python -m pip install --upgrade pip
python -m pip install -r requirements.backend.txt

## STEP 4 - Sanity: boot it manually once
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001
# In a second PowerShell:  Invoke-RestMethod http://127.0.0.1:8001/api/health
# Expect: {"status":"ok","version":"1.0.0"}
# Confirm /readyz too:     Invoke-RestMethod http://127.0.0.1:8001/readyz
# Ctrl+C to stop after the check.

## STEP 5 - Open the firewall to the API port
# Run as ADMIN PowerShell (one-time). Allows public traffic to 8001.
New-NetFirewallRule -DisplayName "ORQEVA API 8001" -Direction Inbound -Protocol TCP -LocalPort 8001 -Action Allow

## STEP 6 - Run it as a persistent Windows service (auto-start + restart)
# The backend must run 24/7. Use NSSM to wrap uvicorn as a service.
#   https://nssm.cc/download - unzip "nssm.exe" into C:\orqeva\deploy\
cd C:\orqeva\deploy
.\nssm.exe install ORQEVA "C:\Program Files\Python311\python.exe" "-m uvicorn backend.main:app --host 0.0.0.0 --port 8001"
# If Python is a Store install or different path, point nssm at:
#   (Get-Command python).Source
# Set the service to run in C:\orqeva:
.\nssm.exe set ORQEVA AppDirectory C:\orqeva
# Let it log to a file (optional but useful):
.\nssm.exe set ORQEVA AppStdout C:\orqeva\logs\out.log
.\nssm.exe set ORQEVA AppStderr C:\orqeva\logs\err.log
.\nssm.exe set ORQEVA AppRotateFiles 1
.\nssm.exe set ORQEVA AppRotateBytes 10485760
# Start it:
New-Item -ItemType Directory -Force -Path C:\orqeva\logs | Out-Null
.\nssm.exe start ORQEVA

## STEP 7 - Confirm the service is healthy
Get-Service ORQEVA                      # Running
Invoke-RestMethod http://127.0.0.1:8001/api/health
Invoke-RestMethod http://127.0.0.1:8001/readyz

## STEP 8 - (Recommended) TLS via Caddy instead of raw :8001
# Windows build of Caddy: https://caddyserver.com/download (Windows amd64).
# 1. Put caddy.exe in C:\caddy, create C:\caddy\Caddyfile with:
#      api.yourdomain.com {
#        reverse_proxy 127.0.0.1:8001
#      }
# 2. Cloudflare DNS:  A record  api  ->  <VPS public IP>  (proxied).
# 3. Run as a service too:
#      C:\caddy\caddy.exe run --config C:\caddy\Caddyfile
#      (or install via https://caddyserver.com/docs/install#windows-service ,
#       sc.exe create caddy ... )
# 4. Optionally close 8001 to the public and only expose 443:
#      Remove-NetFirewallRule -DisplayName "ORQEVA API 8001"
#      New-NetFirewallRule -DisplayName "HTTPS 443" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
# 5. Test:  Invoke-RestMethod https://api.yourdomain.com/api/health

## STEP 9 - Point the frontend at the backend + redeploy
# Local machine only. Edit frontend\.env.local and set:
#   NEXT_PUBLIC_API_URL=http://<VPS_IP>:8001
#   ...or with TLS (preferred): NEXT_PUBLIC_API_URL=https://api.yourdomain.com
# Rebuild + redeploy to Cloudflare Pages (same as before):
#   cd frontend; npm run build; wrangler pages deploy out --project-name orqeva

## STEP 10 - Verify from the internet
# Open https://orqeva.pages.dev, log in as uzorjohnpaul9@gmail.com, open a few
# pages (Trading, Billing, /admin). Dashboards now read live data from the VPS.

## UPDATE the service (new commit)
cd C:\orqeva
git pull
.\nssm.exe restart ORQEVA
# (dependencies rarely change; if requirements.txt moved, re-run Step 3 first)

## LOGS
Get-Content C:\orqeva\logs\out.log -Tail 50 -Wait     # uvicorn stdout
Get-Content C:\orqeva\logs\err.log -Tail 50 -Wait     # errors

## ============================================================================
## HARDENING (before real users)
## ============================================================================
# - TL;DR: get Step 8 (Caddy TLS) up before opening the service to the public,
#   otherwise login credentials cross the internet in plain HTTP.
# - Keep the Windows Firewall on; only allow 8001 (or 443) + RDP.
# - Use a strong ADMIN_PASSWORD; the seed writes it into uzorjohnpaul9@gmail.com
#   user_metadata on every boot (backend/db/database.py seed_admin).
# - Do NOT run uvicorn with --reload in production (service mode never does).
# ============================================================================

## ============================================================================
## WHY SCAN_INTERVAL_MINUTES=60
## ============================================================================
# Twelve Data free tier = 800 calls/day. A single engine scan costs ~57 calls
# (forex 7 x1 + crypto up to 50 symbols). At 60-min cadence you stay well under
# the cap; do not lower it until you upgrade the Twelve Data plan.
# ============================================================================