#!/usr/bin/env bash
# End-to-end checks against a running server: layout sweep, modes, hotspots, sound, chapters, language.
set -uo pipefail
base=${BASE_URL:-http://localhost:4321}
session=${SESSION:-app}
out=${1:-${TMPDIR:-/tmp}/verify-app}
mkdir -p "$out"
failures=0
ab() { agent-browser --session "$session" "$@"; }
check() {
	if [[ "$2" == "$3" ]]; then echo "pass  $1"; else echo "FAIL  $1: expected '$3', got '$2'"; failures=$((failures + 1)); fi
}
value() { ab eval "$1" 2>/dev/null | tail -1 | tr -d '"'; }
ready() { ab wait --fn "document.documentElement.dataset.stage === 'ready'" --timeout 120000 >/dev/null; }

echo "== horizontal overflow, 320 to 1440, both modes"
for mode in film book; do
	for size in 320x568 390x844 768x1024 1024x768 1440x900; do
		ab set viewport "${size%x*}" "${size#*x}" >/dev/null
		ab open "$base/?mode=$mode&gpu=any&debug&tier=low" >/dev/null
		[[ $mode == film ]] && ready
		check "$mode $size has no sideways scroll" "$(value 'String(document.documentElement.scrollWidth <= document.documentElement.clientWidth)')" "true"
	done
done

echo "== book mode"
ab set viewport 390 844 >/dev/null
ab open "$base/?mode=book" >/dev/null
check "book mode does not load the engine" "$(value 'String(performance.getEntriesByType("resource").some((e) => /boot|three/.test(e.name)))')" "false"
check "every narration line is present" "$(value 'String(document.querySelectorAll("[data-beat]").length)')" "16"
check "all illustrations resolve" "$(value 'Promise.all([...document.images].map((i) => { i.loading = "eager"; return i.decode().then(() => 1, () => 0); })).then((r) => String(r.every(Boolean)))')" "true"
ab screenshot --full "$out/book-mobile.png" >/dev/null

echo "== film mode interactions"
ab set viewport 1280 720 >/dev/null
ab open "$base/?mode=film&gpu=any&debug&tier=medium" >/dev/null
ready
ab eval "Promise.all(window.__story.spans.map((s) => window.__story.ready(s.id))).then(() => 'ok')" >/dev/null
check "no chapter is left waiting" "$(value 'document.documentElement.dataset.waiting')" "false"
check "sound starts off" "$(value 'document.querySelector("[data-sound]").getAttribute("aria-pressed")')" "false"
ab click "[data-sound]" >/dev/null
check "sound toggles on" "$(value 'document.querySelector("[data-sound]").getAttribute("aria-pressed")')" "true"
ab click "[data-sound]" >/dev/null
check "sound toggles off" "$(value 'document.querySelector("[data-sound]").getAttribute("aria-pressed")')" "false"
ab click "[data-chapter-link='3']" >/dev/null
sleep 2.5
check "chapter link reaches chapter 4" "$(value '[...document.querySelectorAll("[data-chapter-link]")].findIndex((l) => l.hasAttribute("aria-current")).toString()')" "3"
ab eval "window.__story.seek(0.42, 2); 'ok'" >/dev/null
sleep 1
check "rose hotspot is offered" "$(value 'document.querySelector("[data-hotspot=\"rose.rose\"]").dataset.active')" "true"
ab click "[data-hotspot='rose.rose']" >/dev/null
check "rose hotspot is a real focusable button" "$(value 'String(document.querySelector("[data-hotspot=\"rose.rose\"]").tabIndex)')" "0"
ab eval "window.__story.seek(0.05, 2); 'ok'" >/dev/null
sleep 1
check "hotspot leaves with its chapter" "$(value 'document.querySelector("[data-hotspot=\"rose.rose\"]").dataset.active')" "false"

echo "== reduced motion"
ab set media dark reduced-motion >/dev/null
ab eval "localStorage.removeItem('story-mode'); 'ok'" >/dev/null
ab open "$base/?gpu=any" >/dev/null
check "reduced motion gets the illustrated book" "$(value 'document.documentElement.dataset.mode')" "book"
ab set media dark no-preference >/dev/null

echo "== spanish"
ab open "$base/es/?mode=book" >/dev/null
check "language attribute" "$(value 'document.documentElement.lang')" "es"
check "opening line is translated" "$(value 'document.querySelector("[data-beat=\"universe.opening\"]").textContent.trim()')" "Todos los grandes fueron niños alguna vez…"

echo "== language detection"
agent-browser --session lang-es --args "--lang=es-AR" open "$base/?mode=book" >/dev/null
sleep 1
check "a Spanish browser lands on the Spanish edition" "$(agent-browser --session lang-es eval 'location.pathname' | tail -1 | tr -d '"')" "/es/"
agent-browser --session lang-es eval "document.querySelector('[data-language]').click(); 'ok'" >/dev/null
sleep 1
agent-browser --session lang-es open "$base/?mode=book" >/dev/null
sleep 1
check "choosing English outranks the browser" "$(agent-browser --session lang-es eval 'location.pathname' | tail -1 | tr -d '"')" "/"
agent-browser --session lang-es close >/dev/null 2>&1

echo "== console"
errors=$(ab errors 2>&1 | grep -vcE "^✗? *$")
check "no uncaught page errors" "$errors" "0"

echo "failures: $failures"
exit "$failures"
