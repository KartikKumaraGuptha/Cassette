# PyInstaller spec for the macOS Cassette application.
# Build this spec on macOS (PyInstaller is not a cross-compiler).
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)

hiddenimports = [
    "spotify",
    "spotify.client",
    "spotify.demo",
    "spotify.lyrics",
]
hiddenimports += collect_submodules("keyring.backends")

datas = [
    (str(ROOT / "logo.png"), "."),
    (str(ROOT / "s1.png"), "."),
    (str(ROOT / "s2.png"), "."),
    (str(ROOT / "s3.png"), "."),
    (str(ROOT / "s4.png"), "."),
    (str(ROOT / "s5.png"), "."),
    (str(ROOT / "assets"), "assets"),
]

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
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

app = BUNDLE(
    exe,
    name="Cassette.app",
    icon=str(ROOT / "cassette.icns"),
    bundle_identifier="com.cassette.spotify",
    info_plist={
        "CFBundleDisplayName": "Cassette",
        "CFBundleName": "Cassette",
        "CFBundleIdentifier": "com.cassette.spotify",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSUIElement": True,
    },
)
