#!/bin/bash
# Maintainer-only build. End users need no compiler or package manager.
set -euo pipefail
cd "$(dirname "$0")/.."
test "$(uname -m)" = arm64 || { echo 'Build on an Apple Silicon Mac.'; exit 1; }
ROOT="$PWD"
export MACOSX_DEPLOYMENT_TARGET=26.0
mkdir -p build/downloads build/vendor build/notices dist
fetch() {
  if [ ! -s "build/downloads/$1" ]; then
    curl --fail --location --max-time 180 --retry 2 "$2" -o "build/downloads/$1.partial"
    mv "build/downloads/$1.partial" "build/downloads/$1"
  fi
}
fetch ffmpeg-8.1.2.tar.xz https://ffmpeg.org/releases/ffmpeg-8.1.2.tar.xz
fetch lame-3.100.tar.gz https://downloads.sourceforge.net/project/lame/lame/3.100/lame-3.100.tar.gz
shasum -a 256 -c packaging/sources.sha256
if [ ! -x build/vendor/bin/ffmpeg ] || ! build/vendor/bin/ffmpeg -hide_banner -encoders 2>/dev/null | grep -q ' png '; then
  [ -d build/lame-3.100 ] || tar -xf build/downloads/lame-3.100.tar.gz -C build
  (cd build/lame-3.100
   ./configure --prefix="$ROOT/build/vendor" --disable-shared --enable-static --disable-frontend
   make -j4 && make install)
  [ -d build/ffmpeg-8.1.2 ] || tar -xf build/downloads/ffmpeg-8.1.2.tar.xz -C build
  (cd build/ffmpeg-8.1.2
   PKG_CONFIG_PATH="$ROOT/build/vendor/lib/pkgconfig" ./configure \
     --prefix="$ROOT/build/vendor" --arch=arm64 --cc=clang \
     --disable-autodetect --disable-shared --enable-static --disable-doc --disable-debug \
     --disable-ffplay --disable-network --disable-avdevice --enable-libmp3lame --enable-zlib \
     --extra-cflags="-I$ROOT/build/vendor/include -mmacosx-version-min=26.0" \
     --extra-ldflags="-L$ROOT/build/vendor/lib -mmacosx-version-min=26.0"
   make -j4 && make install)
fi
cp build/ffmpeg-8.1.2/COPYING.LGPLv2.1 build/notices/FFmpeg-LGPL-2.1.txt
cp build/lame-3.100/COPYING build/notices/LAME-LICENSE.txt
cp packaging/build-arm64.sh build/notices/
cp build/downloads/ffmpeg-8.1.2.tar.xz build/downloads/lame-3.100.tar.gz build/notices/
build/vendor/bin/ffmpeg -buildconf 2> build/notices/FFmpeg-build.txt
"${BUILD_PYTHON:-/opt/homebrew/bin/python3}" -m venv .build-venv
.build-venv/bin/python -m pip install -r packaging/requirements.txt
.build-venv/bin/python packaging/collect-notices.py
export PYINSTALLER_CONFIG_DIR="$ROOT/build/pyinstaller-cache"
.build-venv/bin/python -m PyInstaller --noconfirm --clean packaging/app.spec
.build-venv/bin/python packaging/verify-bundle.py
env PATH=/usr/bin:/bin 'dist/Multitrack Audio Exporter.app/Contents/MacOS/Multitrack Audio Exporter' --smoke-test
ditto -c -k --sequesterRsrc --keepParent 'dist/Multitrack Audio Exporter.app' \
  'dist/Multitrack-Audio-Exporter-0.1.0-macOS26-arm64.zip'
# Keep filenames relative to the download folder, not the source checkout.
(cd dist && shasum -a 256 -- *.zip > SHA256SUMS.txt)
