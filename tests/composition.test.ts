import { describe, expect, it } from "vitest";

import { shotToVector, solveShot, SHOT_CHANNELS, tallness, type Viewport } from "#engine/ResponsiveComposition";
import { CHAPTERS } from "#story/chapters";
import type { Shot } from "#story/types";

const SHOT: Shot = { target: [0, 1, 0], azimuth: 0, elevation: 0, fit: 2, placeX: 0, placeY: 0, roll: 0, fov: 24, focus: 1, aperture: 0.03 };

/**
 * Builds a viewport.
 * @param width Width in pixels.
 * @param height Height in pixels.
 * @param inset Top and bottom safe-area inset.
 * @returns The viewport.
 */
function viewport(width: number, height: number, inset = 0): Viewport {
	return { width, height, safeTop: inset, safeRight: 0, safeBottom: inset, safeLeft: 0 };
}

/**
 * Half-extent the frame covers at the target plane, along the narrower screen axis.
 * @param shot The shot.
 * @param view The viewport.
 * @returns World units from the frame's centre to its nearest edge.
 */
function visibleRadius(shot: Shot, view: Viewport): number {
	const solved = solveShot(Float64Array.from(shotToVector(shot)), view);
	const distance = Math.hypot(solved.position[0] - shot.target[0], solved.position[1] - shot.target[1], solved.position[2] - shot.target[2]);
	const tangent = Math.tan((shot.fov * Math.PI) / 360);
	return distance * Math.min(tangent, tangent * (view.width / view.height));
}

describe("responsive composition", () => {
	it.each([
		[1920, 1080],
		[1440, 900],
		[820, 1180],
		[390, 844],
		[320, 568],
		[2560, 1080],
	])("keeps the fit radius in frame at %i x %i", (width, height) => {
		expect(visibleRadius(SHOT, viewport(width, height))).toBeCloseTo(SHOT.fit, 5);
	});

	it("backs the lens away on a portrait screen instead of cropping", () => {
		const wide = solveShot(Float64Array.from(shotToVector(SHOT)), viewport(1600, 900));
		const tall = solveShot(Float64Array.from(shotToVector(SHOT)), viewport(390, 844));
		expect(tall.position[2]).toBeGreaterThan(wide.position[2] * 1.5);
	});

	it("leaves room for safe areas", () => {
		const plain = solveShot(Float64Array.from(shotToVector(SHOT)), viewport(1600, 900));
		const notched = solveShot(Float64Array.from(shotToVector(SHOT)), viewport(1600, 900, 60));
		expect(notched.position[2]).toBeGreaterThan(plain.position[2]);
	});

	it("blends shots continuously across aspect ratios", () => {
		expect(tallness(1.78)).toBe(0);
		expect(tallness(0.46)).toBe(1);
		for (let aspect = 0.5; aspect < 1.5; aspect += 0.01) {
			expect(Math.abs(tallness(aspect + 0.01) - tallness(aspect))).toBeLessThan(0.05);
		}
	});

	it("gives every key a complete vector", () => {
		for (const chapter of CHAPTERS) {
			for (const key of chapter.shots) {
				const vector = shotToVector({ ...key.wide, ...key.tall });
				expect(vector).toHaveLength(SHOT_CHANNELS);
				expect(vector.every(Number.isFinite)).toBe(true);
			}
		}
	});
});
