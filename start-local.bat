@echo off
setlocal
title ORQEVA - Local Backend + Tunnel
cd /d "%~dp0"

echo ============================================================
echo   ORQEVA - START LOCAL BACKEND
echo   Ctrl+C here when done. Site goes offline when window closes.
echo ============================================================
echo.

REM --- Keep the PC awake while the site is running ------------
powercfg /change standby-timeout-ac 0
powercfg /change standby-timeout-dc 0
echo [i] Sleep disabled while running (re-enabled on exit).

REM --- Start the FastAPI backend (detached, killed on exit) ---
echo [i] Starting backend on http://127.0.0.1:8001 ...
start "ORQEVA-backend" /min cmd /c "cd /d ""%~dp0"" && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001"
timeout /t 6 /nobreak >nul

REM --- Start Cloudflare quick tunnel --------------------------
echo.
echo [i] Starting Cloudflare tunnel. A URL like https://xxx.trycloudflare.com
echo     will appear below. IF it changed, rebuild the frontend:
echo       cd frontend ^&^& set NEXT_PUBLIC_API_URL=^<new-url^> ^&^& npm run build
echo       npx wrangler pages deploy out --project-name orqeva
echo.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --no-autoupdate --url http://127.0.0.1:8001
REM --- Reached only after cloudflared exits -------------------
echo.
echo [i] Stopping backend...
taskkill /F /FI "WINDOWTITLE eq ORQEVA-backend" >nul 2>&1
echo [i] Re-enabling sleep...
powercfg /change standby-timeout-ac 30
powercfg /change standby-timeout-dc 15
echo [i] Done.
endlocal