#!/usr/bin/env bash
# Captures the story at exact positions: scripts/shoot.sh <width> <height> <outdir> <tier> <progress>...
# Relies on the ?debug handle, which pins scroll and stage time so frames are repeatable.
set -euo pipefail
width=$1; height=$2; out=$3; tier=$4; shift 4
base=${BASE_URL:-http://localhost:4321}
session=${SESSION:-story}
query=${QUERY:-}
mkdir -p "$out"
ab() { agent-browser --session "$session" "$@"; }
ab set viewport "$width" "$height" >/dev/null
ab open "$base/?mode=film&gpu=any&debug&tier=$tier$query" >/dev/null
ab wait --fn "document.documentElement.dataset.stage === 'ready'" --timeout 120000 >/dev/null
ab eval "Promise.all(window.__story.spans.map(s => window.__story.ready(s.id))).then(() => 'ok')" >/dev/null
for progress in "$@"; do
	ab eval "window.__story.seek($progress, 2.5); new Promise(r => setTimeout(r, ${SETTLE:-1300})).then(() => 'ok')" >/dev/null
	ab screenshot "$out/p${progress}-${width}x${height}.png" >/dev/null
	echo "$out/p${progress}-${width}x${height}.png"
done
ab eval "JSON.stringify(window.__story.stats())"
