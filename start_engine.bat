@echo off
echo ========================================
echo   AI Trading Engine - Starting...
echo ========================================
echo.
echo To stop: Press Ctrl+C
echo.
cd /d "%~dp0"
python live_engine.py --interval 15
pause
