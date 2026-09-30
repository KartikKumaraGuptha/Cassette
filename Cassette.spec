# PyInstaller build definition for the existing Cassette application.
# Application Python/UI source is intentionally not modified by this file.

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)

hiddenimports = ["spotify",
"spotify.client",
"spotify.demo",
"spotify.lyrics",]
hiddenimports += collect_submodules("keyring.backends")

# Keep the user-provided guide images and transparent logo beside the EXE.
datas = [
    (str(ROOT / "logo.png"), "."),
    (str(ROOT / "s1.png"), "."),
    (str(ROOT / "s2.png"), "."),
    (str(ROOT / "s3.png"), "."),
    (str(ROOT / "s4.png"), "."),
    (str(ROOT / "s5.png"), "."),
    (str(ROOT / "assets"), "assets"),
]

 # PySide6 is handled by PyInstaller's Qt hooks. This is the Windows build;
# Windows-specific compositor and gesture code is isolated at runtime.
a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Cassette",
    icon=str(ROOT / "cassette.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
