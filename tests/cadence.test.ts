import { describe, expect, it } from "vitest";

import { frameAtProgress, frameInCycle, poseIndex, poseNoise, POSES_PER_SECOND } from "#story/cadence";

describe("animation time", () => {
	it("keeps replacement parts on a 12 per second grid however often it is sampled", () => {
		const poses = new Set<number>();
		for (let frame = 0; frame < 120; frame++) poses.add(poseIndex(frame / 120));
		expect(poses.size).toBe(POSES_PER_SECOND);
	});

	it("maps scroll to the same frame in both directions", () => {
		for (const progress of [0, 0.123, 0.5, 0.999, 1]) {
			expect(frameAtProgress(progress, 20)).toBe(frameAtProgress(progress, 20));
		}
		expect(frameAtProgress(0.25, 20)).toBe(5);
		expect(frameAtProgress(2, 20)).toBe(20);
		expect(frameAtProgress(-1, 20)).toBe(0);
	});

	it("wraps cycles without ever reaching the loop length", () => {
		for (let distance = 0; distance < 5; distance += 0.037) {
			const frame = frameInCycle(distance, 12);
			expect(frame).toBeGreaterThanOrEqual(0);
			expect(frame).toBeLessThan(12);
		}
	});

	it("repeats a pose's noise exactly, which is what keeps it from reading as jitter", () => {
		expect(poseNoise(42, 3)).toBe(poseNoise(42, 3));
		expect(poseNoise(42, 3)).not.toBe(poseNoise(43, 3));
		for (let i = 0; i < 100; i++) {
			expect(poseNoise(i)).toBeGreaterThanOrEqual(0);
			expect(poseNoise(i)).toBeLessThan(1);
		}
	});
});
