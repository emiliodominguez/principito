#!/usr/bin/env bash
# Renders the illustrated edition: one still per chapter and aspect, taken from the real film at a held moment.
# Used by book mode, by reduced-motion readers and by devices without WebGL.
set -euo pipefail
base=${BASE_URL:-http://localhost:4321}
session=${SESSION:-stills}
capture_dir=$(mktemp -d)
ab() { agent-browser --session "$session" "$@"; }

capture() {
	local suffix=$1 width=$2 height=$3
	ab set viewport "$width" "$height" >/dev/null
	ab open "$base/?mode=film&gpu=any&debug&tier=high&still" >/dev/null
	ab wait --fn "document.documentElement.dataset.stage === 'ready'" --timeout 120000 >/dev/null
	ab eval "Promise.all(window.__story.spans.map(s => window.__story.ready(s.id))).then(() => 'ok')" >/dev/null
	# Moments chosen for composition, with narration hidden: the book sets the text itself.
	ab eval "document.documentElement.dataset.still = 'true'; 'ok'" >/dev/null
	for pair in universe:0.03 planet:0.2 rose:0.425 journey:0.53 fox:0.79 finale:0.985; do
		ab eval "window.__story.seek(${pair#*:}, 2.5); new Promise(r => setTimeout(r, 1500)).then(() => 'ok')" >/dev/null
		ab screenshot "$capture_dir/${pair%:*}-$suffix.png" >/dev/null
		node -e "require('sharp')('$capture_dir/${pair%:*}-$suffix.png').webp({ quality: 80, effort: 5 }).toFile('public/fallback/${pair%:*}-$suffix.webp').then(() => console.log('${pair%:*}-$suffix'))"
	done
}

capture wide 1600 900
capture tall 720 1120
