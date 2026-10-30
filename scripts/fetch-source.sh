#!/bin/bash
# Prepares src/ from the official source tarball (Debian style, no git history):
#   1. downloads and verifies chromium-$VERSION.tar.xz,
#   2. extracts it to src/,
#   3. fetches the Android-only DEPS the Linux tarball omits,
#   4. applies patches/series with quilt.
#
# Usage: scripts/fetch-source.sh VERSION
set -euo pipefail
VERSION=${1:?usage: $0 VERSION}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
URL=https://commondatastorage.googleapis.com/chromium-browser-official
TARBALL=chromium-$VERSION.tar.xz
export PATH="$ROOT/depot_tools:$PATH" DEPOT_TOOLS_UPDATE=0

if [ ! -d "$ROOT/depot_tools" ]; then
  git clone --depth=1 https://chromium.googlesource.com/chromium/tools/depot_tools.git \
    "$ROOT/depot_tools"
  "$ROOT/depot_tools/ensure_bootstrap"
fi

# depot_tools (gn, autoninja) locate src/ through a .gclient file. It is never
# used for `gclient sync`.
if [ ! -f "$ROOT/.gclient" ]; then
  cat > "$ROOT/.gclient" <<GCLIENT
solutions = [{"name": "src", "url": None, "managed": False}]
target_os = ["android"]
GCLIENT
fi

mkdir -p "$ROOT/dl"
cd "$ROOT/dl"
if [ ! -f "$TARBALL" ]; then
  curl -fL -o "$TARBALL.part" "$URL/$TARBALL"
  mv "$TARBALL.part" "$TARBALL"
fi
curl -sSfL -o "$TARBALL.hashes" "$URL/$TARBALL.hashes"
grep "^sha256 " "$TARBALL.hashes" | awk "{print \$2\"  \"\$3}" | sha256sum -c -

if [ -e "$ROOT/src" ]; then
  echo "$ROOT/src already exists; move it away first." >&2
  exit 1
fi
mkdir "$ROOT/src"
xz -T0 -dc "$TARBALL" | tar -x -C "$ROOT/src" --strip-components=1

python3 "$ROOT/scripts/android_deps.py" "$ROOT/src"
ln -sfn ../patches "$ROOT/src/patches"
"$ROOT/scripts/quilt" push -a
