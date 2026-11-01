#!/usr/bin/env bash
# What a first-time reader gets: scrolls immediately, with nothing preloaded, and records every main-thread
# stall with the story position it happened at. Also reports how often the render scale changed.
set -euo pipefail
base=${BASE_URL:-http://localhost:4321}
session=${SESSION:-cold}
tier=${1:-high}
ab() { agent-browser --session "$session" "$@"; }
ab set viewport 1440 900 "${DPR:-2}" >/dev/null
ab eval "'ready'" >/dev/null 2>&1 || true
ab open "$base/?mode=film&debug&gpu=any&tier=$tier" >/dev/null
ab wait --fn "document.documentElement.dataset.stage === 'ready'" --timeout 120000 >/dev/null
ab eval "
	new Promise((resolve) => {
		const stalls = [];
		new PerformanceObserver((list) => {
			for (const entry of list.getEntries()) stalls.push({ at: Number(window.__story.progress().toFixed(2)), ms: Math.round(entry.duration) });
		}).observe({ entryTypes: ['longtask'] });
		const duration = 26000;
		const height = document.documentElement.scrollHeight - innerHeight;
		const start = performance.now();
		function step(now) {
			const t = (now - start) / duration;
			window.scrollTo(0, height * Math.min(1, t));
			if (t < 1) requestAnimationFrame(step);
			else setTimeout(() => resolve(JSON.stringify({ stalls: stalls.length, worst: Math.max(0, ...stalls.map((s) => s.ms)), total: stalls.reduce((a, s) => a + s.ms, 0), list: stalls.filter((s) => s.ms > 60), scale: window.__story.stats().scale })), 400);
		}
		requestAnimationFrame(step);
	})
" | tail -1
