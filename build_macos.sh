#!/bin/bash
set -e
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
rm -rf cassette.iconset
mkdir cassette.iconset
sips -z 16 16 logo.png --out cassette.iconset/icon_16x16.png
sips -z 32 32 logo.png --out cassette.iconset/icon_16x16@2x.png
sips -z 32 32 logo.png --out cassette.iconset/icon_32x32.png
sips -z 64 64 logo.png --out cassette.iconset/icon_32x32@2x.png
sips -z 128 128 logo.png --out cassette.iconset/icon_128x128.png
sips -z 256 256 logo.png --out cassette.iconset/icon_128x128@2x.png
sips -z 256 256 logo.png --out cassette.iconset/icon_256x256.png
sips -z 512 512 logo.png --out cassette.iconset/icon_256x256@2x.png
sips -z 512 512 logo.png --out cassette.iconset/icon_512x512.png
sips -z 1024 1024 logo.png --out cassette.iconset/icon_512x512@2x.png
iconutil -c icns cassette.iconset -o cassette.icns
rm -rf cassette.iconset
python3 -m PyInstaller --noconfirm --clean Cassette_mac.spec
open dist/Cassette.app
