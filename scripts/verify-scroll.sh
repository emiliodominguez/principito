#!/usr/bin/env bash
# Drives the page with real scrolling. Proves the story is a pure function of position: a frame
# reached going forward must match the frame reached going backward, pixel for pixel.
set -euo pipefail
out=${1:-${TMPDIR:-/tmp}/verify}
base=${BASE_URL:-http://localhost:4321}
session=${SESSION:-verify}
mkdir -p "$out"
ab() { agent-browser --session "$session" "$@"; }
ab set viewport 1280 720 >/dev/null
ab open "$base/?mode=film&gpu=any&debug&tier=medium" >/dev/null
ab wait --fn "document.documentElement.dataset.stage === 'ready'" --timeout 120000 >/dev/null
ab eval "Promise.all(window.__story.spans.map(s => window.__story.ready(s.id))).then(() => 'ok')" >/dev/null
# Freeze stage time so only scroll position can change the picture.
ab eval "window.__story.seek(0, 3); 'frozen'" >/dev/null
scroll_to() {
	ab eval "window.scrollTo(0, (document.documentElement.scrollHeight - innerHeight) * $1); new Promise(r => setTimeout(r, 1600)).then(() => window.__story.progress())" | tail -1
}
for position in 0.3 0.62 0.86; do
	echo "forward  $position -> $(scroll_to "$position")"
	ab screenshot "$out/forward-$position.png" >/dev/null
done
scroll_to 1 >/dev/null
for position in 0.86 0.62 0.3; do
	echo "backward $position -> $(scroll_to "$position")"
	ab screenshot "$out/backward-$position.png" >/dev/null
done
node -e "
const sharp = require('sharp');
(async () => {
	for (const p of ['0.3', '0.62', '0.86']) {
		const a = await sharp('$out/forward-' + p + '.png').raw().toBuffer();
		const b = await sharp('$out/backward-' + p + '.png').raw().toBuffer();
		let sum = 0, max = 0;
		for (let i = 0; i < a.length; i++) { const d = Math.abs(a[i] - b[i]); sum += d; if (d > max) max = d; }
		console.log('position', p, 'mean difference', (sum / a.length).toFixed(3), 'max', max);
	}
})();
"
