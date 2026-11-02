@echo off
REM Start the ORQEVA MT5 bridge on the Windows VPS that runs the Exness terminal.
REM Required: MT5_BRIDGE_TOKEN (shared with the Railway backend).
REM Optional: MT5_TERMINAL_PATH, MT5_SYMBOL_SUFFIX (default m), MT5_DEFAULT_SERVER.
setlocal
cd /d "%~dp0.."

if "%MT5_BRIDGE_TOKEN%"=="" (
  echo [x] MT5_BRIDGE_TOKEN is not set. Export it before starting the bridge.
  exit /b 1
)

python -m uvicorn bridge.mt5_bridge:app --host 127.0.0.1 --port 8100
