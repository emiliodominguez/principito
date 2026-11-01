import { describe, expect, it } from "vitest";

import { CHAPTERS } from "#story/chapters";
import { createTrack, layoutChapters, progressIn, smoothstep, spanAt } from "#story/timeline";

describe("story layout", () => {
	it("covers the whole timeline without gaps", () => {
		const spans = layoutChapters(CHAPTERS);
		expect(spans[0]?.start).toBe(0);
		expect(spans.at(-1)?.end).toBeCloseTo(1);
		spans.slice(1).forEach((span, index) => {
			expect(span.start).toBeCloseTo(spans[index]?.end ?? -1);
		});
	});

	it("keeps every chapter's keys in reading order", () => {
		for (const chapter of CHAPTERS) {
			const times = chapter.shots.map((shot) => shot.at);
			expect(times).toEqual(times.toSorted((a, b) => a - b));
			expect(new Set(times).size).toBe(times.length);
			for (const beat of chapter.beats) expect(beat.to).toBeGreaterThan(beat.from);
		}
	});

	it("gives a boundary position to the later chapter, and the very end to the last", () => {
		const spans = layoutChapters(CHAPTERS);
		expect(spanAt(spans, spans[1]?.start ?? 0).id).toBe("planet");
		expect(spanAt(spans, 1).id).toBe("finale");
	});
});

describe("camera tracks", () => {
	const out = new Float64Array(1);

	it("passes exactly through its keys", () => {
		const track = createTrack([0, 0.5, 1], [[2], [8], [3]]);
		expect(track.sample(0.5, out)[0]).toBeCloseTo(8);
		expect(track.sample(1, out)[0]).toBeCloseTo(3);
	});

	it("comes to rest at the end, so the film never stops dead", () => {
		const track = createTrack([0, 0.5, 1], [[0], [4], [10]]);
		const last = track.sample(1, out)[0] ?? 0;
		const before = track.sample(0.999, out)[0] ?? 0;
		expect(last - before).toBeLessThan(0.002);
	});

	it("never overshoots between keys, so the camera settles on a shot", () => {
		const track = createTrack([0, 0.4, 0.5, 1], [[0], [1], [1], [5]]);
		for (let t = 0; t <= 1; t += 0.01) {
			const value = track.sample(t, out)[0] ?? 0;
			expect(value).toBeGreaterThanOrEqual(-1e-9);
			expect(value).toBeLessThanOrEqual(5 + 1e-9);
			if (t >= 0.4 && t <= 0.5) expect(value).toBeCloseTo(1, 6);
		}
	});

	it("gives the same answer forward and backward", () => {
		const track = createTrack([0, 0.3, 1], [[1], [4], [2]]);
		const forward = [0.1, 0.5, 0.9].map((t) => track.sample(t, out)[0]);
		const backward = [0.9, 0.5, 0.1].map((t) => track.sample(t, out)[0]).toReversed();
		expect(backward).toEqual(forward);
	});
});

describe("ranges", () => {
	it("clamps progress and handles an empty range", () => {
		expect(progressIn(5, 0, 2)).toBe(1);
		expect(progressIn(-1, 0, 2)).toBe(0);
		expect(progressIn(1, 1, 1)).toBe(1);
		expect(smoothstep(0, 1, 0.5)).toBeCloseTo(0.5);
	});
});
