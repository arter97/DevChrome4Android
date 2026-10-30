#!/bin/bash
# Configures and builds the APK.
#
# Usage: [VARIANT=official|release] [GEN_ONLY=1] scripts/build.sh [ninja targets...]
#
# The args of a variant are args/common.gn + args/$VARIANT.gn, written to
# src/out/<Variant>/args.gn. Default: official. GEN_ONLY=1 stops after gn gen.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
export PATH="$ROOT/depot_tools:$PATH" DEPOT_TOOLS_UPDATE=0
VARIANT=${VARIANT:-official}
[ -f "$ROOT/args/$VARIANT.gn" ] || { echo "unknown VARIANT=$VARIANT" >&2; exit 1; }
OUT=out/${VARIANT^}
cd "$ROOT/src"
mkdir -p "$OUT"
ARGS=$(cat "$ROOT/args/common.gn" "$ROOT/args/$VARIANT.gn")
[ "$ARGS" = "$(cat "$OUT/args.gn" 2>/dev/null)" ] || printf "%s\n" "$ARGS" > "$OUT/args.gn"
gn gen "$OUT"
[ "${GEN_ONLY:-0}" = 1 ] && exit 0
autoninja -C "$OUT" "${@:-chrome_public_apk}"
