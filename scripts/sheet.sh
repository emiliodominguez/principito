#!/usr/bin/env bash
# Contact sheet of story positions: scripts/sheet.sh <name> <width> <height> <tier> <columns> <tile-width> <progress>...
set -euo pipefail
name=$1; width=$2; height=$3; tier=$4; columns=$5; tile=$6; shift 6
out=${OUT_ROOT:-${TMPDIR:-/tmp}/shots}/$name
scripts/shoot.sh "$width" "$height" "$out" "$tier" "$@" | tail -1
files=()
for progress in "$@"; do files+=("$out/p${progress}-${width}x${height}.png"); done
node scripts/montage.mjs "$out.png" "$columns" "$tile" "${files[@]}"
