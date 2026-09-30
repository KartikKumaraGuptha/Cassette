CASSETTE WINDOWS RELEASE BUILD

The application source has not been modified for this release build.
The added files only define packaging/installer behavior.

BUILD MACHINE REQUIREMENTS
- Windows 10/11 x64
- Python 3.11+ (build machine only)
- Inno Setup 6 (build machine only)

BUILD
1. Open this folder on a Windows build machine.
2. Double-click BUILD_INSTALLER.bat.
3. The finished installer will be:
   installer_output\Cassette_Setup.exe

END USER
The installed user does NOT need Python, pip, PySide6, or the source code.
Cassette_Setup.exe installs the PyInstaller-built application and its runtime.

ASSETS
logo.png and s1.png, s2.png, s3.png, s4.png, s5.png are installed beside
Cassette.exe so the existing setup-guide asset lookup continues to work.

ONE-FILE FRIEND RELEASE
=======================
The final file intended for sharing is:
    Cassette_Setup.exe

Build it on Windows using BUILD_INSTALLER.bat, or use the GitHub Actions workflow:
    .github/workflows/build-windows-installer.yml

The installer bundles the Python runtime and application dependencies. Friends do not need Python installed.
