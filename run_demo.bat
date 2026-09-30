@echo off
setlocal
cd /d "%~dp0"
set "DEMO_MODE=1"
python main.py
if errorlevel 1 (
    echo.
    echo Cassette stopped with an error. Check the message above.
    pause
    exit /b 1
)
endlocal
