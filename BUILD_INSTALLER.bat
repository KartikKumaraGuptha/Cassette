@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Cassette - Windows Installer Build
echo ========================================

echo.
echo [1/4] Checking Python...
where py >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python Launcher was not found.
    echo Install Python 3.11+ for the BUILD MACHINE only, then run this again.
    exit /b 1
)

set PY=py

%PY% -m pip install --upgrade pip
if errorlevel 1 exit /b 1

 echo.
echo [2/4] Installing build dependencies...
%PY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

 echo.
echo [3/4] Building the Windows application with PyInstaller...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
%PY% -m PyInstaller --noconfirm --clean Cassette.spec
if errorlevel 1 exit /b 1

 echo.
echo [4/4] Building Cassette_Setup.exe...
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe

if not defined ISCC (
    echo ERROR: Inno Setup 6 was not found.
    echo Install Inno Setup 6 on this BUILD MACHINE, then run this again.
    exit /b 1
)

if exist installer_output rmdir /s /q installer_output
"%ISCC%" installer.iss
if errorlevel 1 exit /b 1

echo.
echo ========================================
echo BUILD COMPLETE
echo ========================================
echo Installer: %CD%\installer_output\Cassette_Setup.exe
exit /b 0
