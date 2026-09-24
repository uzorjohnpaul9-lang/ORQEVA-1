# ============================================================================
# VPS DEPLOYMENT GUIDE - ORQEVA backend (FastAPI on a single Ubuntu VPS)
# ============================================================================
# The frontend is served statically by Cloudflare Pages (no backend there).
# This guide runs ONLY the Python API on the VPS with Docker + docker compose.
# After this is live, set frontend/.env.local NEXT_PUBLIC_API_URL to
# http://<VPS_IP>:8001 and redeploy Cloudflare Pages.
#
# Assumes: an Ubuntu 22.04/24.04 VPS with a public IP (e.g. $5-10/mo plan).
# ============================================================================

## STEP 1 - Prep the server (one-time)
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git curl ufw

## STEP 2 - Install Docker (one-time)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker        # or log out/in so 'docker' works without sudo

## STEP 3 - Get the code (one-time)
git clone <your-repo-url> /opt/orqeva && cd /opt/orqeva

## STEP 4 - Create the backend .env (paste your REAL keys)
# IMPORTANT: use the modern Supabase publishable + secret keys (NOT legacy
# anon/service_role). Substitutions from the local C:\Users\Munachi\ai-trading-system\.env.
cat > /opt/orqeva/.env << 'EOF'
SUPABASE_URL=https://crysjnakhwveokjrydyw.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_VYLZNBFGZJ9UFV3zIEM_1g_pV9fBW6J
SUPABASE_SECRET_KEY=sb_secret_********PASTE_ME********
SECRET_KEY=********PASTE_ME********
ENCRYPTION_KEY=********PASTE_ME********
ADMIN_EMAIL=admin@demo.com
ADMIN_PASSWORD=********PASTE_ME********
ALPACA_API_KEY=********PASTE_ME********
ALPACA_SECRET_KEY=********PASTE_ME********
ALPACA_BASE_URL=https://paper-api.alpaca.markets
TWELVE_DATA_API_KEY=********PASTE_ME********
SCAN_ENABLED=1
SCAN_INTERVAL_MINUTES=60
SCAN_COOLDOWN_HOURS=4
TRADING_ENABLED=false
EOF
# Then:  nano /opt/orqeva/.env   and replace every ********PASTE_ME******** value.

## STEP 5 - Build + start the backend container
cd /opt/orqeva
docker compose -f deploy/docker-compose.backend.yml up -d --build

## STEP 6 - Confirm it is healthy
docker compose -f deploy/docker-compose.backend.yml ps
curl -s http://127.0.0.1:8001/api/health   # -> {"status":"ok","version":"1.0.0"}
curl -s http://127.0.0.1:8001/readyz        # -> {"status":"ready","database":"up"}

## STEP 7 - Open the firewall to the API port (public users reach it)
sudo ufw allow OpenSSH
sudo ufw allow 8001/tcp
sudo ufw --force enable

## STEP 8 - (Recommended) add a reverse proxy + TLS via Caddy for a clean
#           https://api.yourdomain.com instead of exposing raw :8001.
# 1. Edit deploy/Caddyfile.api : replace api.yourdomain.com with your real sub-domain.
# 2. Create DNS record on Cloudflare:  A record api -> <VPS_IP>  (proxied).
# 3. Bring it up (proxy + backend together; raw :8001 is then closed off):
#      docker compose -f deploy/docker-compose.backend.yml -f deploy/docker-compose.proxy.yml up -d --build
# 4. flask the backend health via the public domain:
#      curl -s https://api.yourdomain.com/api/health

## STEP 9 - Point the frontend at the backend
# Edit frontend/.env.local and add:
#   NEXT_PUBLIC_API_URL=https://api.yourdomain.com   (preferred, after Step 8)
#   ...or without TLS for now:  NEXT_PUBLIC_API_URL=http://<VPS_IP>:8001
# Rebuild + redeploy frontend/out to Cloudflare Pages (same as before).

## STEP 10 - Verify from the internet
# Open https://orqeva.pages.dev in a browser, log in, open Trading/Billing pages.
# The dashboards now read live data from the VPS API.

## STOP / UPDATE the service
docker compose -f deploy/docker-compose.backend.yml down          # stop
cd /opt/orqeva && git pull && docker compose -f deploy/docker-compose.backend.yml up -d --build   # update

## LOGS
docker compose -f deploy/docker-compose.backend.yml logs -f backend

## ============================================================================
## HARDENING CHEATSHEET (before going live with real users)
## ============================================================================
# - Generate FRESH SECRET_KEY + ENCRYPTION_KEY on the VPS:
#     python3 -c "import secrets;print(secrets.token_hex(32))"        # SECRET_KEY
#     python3 -c "import base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"  # ENCRYPTION_KEY
# - Set ADMIN_PASSWORD to a strong unique value.
# - TLS via Caddy (Step 8) so user passwords never cross plain HTTP.
# - If you use the raw :8001 path short-term, the API serves HTTPS only
#   once behind Caddy; otherwise credentials travel over HTTP until TLS is up.
# ============================================================================

## ============================================================================
## WHY SCAN_INTERVAL_MINUTES=60 (read before raising it)
## ============================================================================
# Engine scan cost per run (Twelve Data free tier = 800 calls/day):
#   forex 7 pairs x1 + crypto up to 50 symbols = ~57 calls
# Every scan consumes budget. At 60-min = ~1,368/day worst case if markets
# are always open (only during market hours in practice), which can exceed
# the 800 cap. Keep 60-120 min on the FREE tier; upgrade to Twelve Data Grow
# ($29/mo) before you need faster scans.
# ============================================================================