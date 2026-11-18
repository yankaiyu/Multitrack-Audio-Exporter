#!/bin/bash
# Resize the committed master with native macOS tools; no image-library dependency.
set -euo pipefail
cd "$(dirname "$0")/.."
iconset="$(mktemp -d "${TMPDIR:-/tmp}/mae-icon.XXXXXX")/AppIcon.iconset"
mkdir -p "$iconset"
trap 'rm -rf "${iconset%/*}"' EXIT
for size in 16 32 128 256 512; do
  /usr/bin/sips -z "$size" "$size" assets/app-icon.png --out "$iconset/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  /usr/bin/sips -z "$double" "$double" assets/app-icon.png --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
done
/usr/bin/iconutil -c icns "$iconset" -o assets/app-icon.icns
/usr/bin/sips -z 128 128 assets/app-icon.png --out web/app-icon.png >/dev/null
echo 'App icon and web favicon generated.'
