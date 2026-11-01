#!/usr/bin/env bash
# True per-frame cost, GPU included. rAF pacing cannot show this in a headless browser, because nothing
# waits for the GPU there, so each frame here is read back, which blocks until the GPU has finished it.
# Usage: DPR=2 scripts/measure-gpu.sh "high 1440 900" ...
set -euo pipefail
base=${BASE_URL:-http://localhost:4321}
session=${SESSION:-perf}
ab() { agent-browser --session "$session" "$@"; }
specs=("$@")
[[ ${#specs[@]} -eq 0 ]] && specs=("high 1440 900")
for spec in "${specs[@]}"; do
	read -r tier width height <<<"$spec"
	ab set viewport "$width" "$height" "${DPR:-1}" >/dev/null
	ab open "$base/?mode=film&debug&gpu=any&tier=$tier" >/dev/null
	ab wait --fn "document.documentElement.dataset.stage === 'ready'" --timeout 120000 >/dev/null
	ab eval "Promise.all(window.__story.spans.map((s) => window.__story.ready(s.id))).then(() => 'ok')" >/dev/null
	result=$(ab eval "JSON.stringify(window.__story.probe([0.03, 0.2, 0.42, 0.56, 0.72, 0.8, 0.98]))" | tail -1)
	echo "$tier ${width}x${height} @${DPR:-1}x: $result"
done
