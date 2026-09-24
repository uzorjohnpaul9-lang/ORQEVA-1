@echo off
echo ============================================
echo  AI Trading System - TensorFlow Install Fix
echo ============================================
echo.

:: Check if venv exists, create if not
if not exist "C:\venv\trading\Scripts\pip.exe" (
    echo Creating virtual environment at C:\venv\trading ...
    python -m venv C:\venv\trading
)

echo Installing TensorFlow in venv (short path)...
C:\venv\trading\Scripts\pip.exe install tensorflow

echo.
echo Verifying install...
C:\venv\trading\Scripts\python.exe -c "import tensorflow; print(f'TensorFlow {tensorflow.__version__} installed successfully')"

echo.
echo To use this venv, run:
echo   C:\venv\trading\Scripts\activate
echo   pip install -r requirements.txt
echo.
pause
