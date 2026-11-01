import { smoothstep } from "#story/timeline";
import type { Shot, Vec3 } from "#story/types";

/** The numbers the camera actually needs, solved for one viewport. */
export interface SolvedShot {
	readonly position: Vec3;
	readonly target: Vec3;
	readonly fov: number;
	readonly roll: number;
	readonly shiftX: number;
	readonly shiftY: number;
	readonly focusDistance: number;
	readonly aperture: number;
}

export interface Viewport {
	readonly width: number;
	readonly height: number;
	readonly safeTop: number;
	readonly safeRight: number;
	readonly safeBottom: number;
	readonly safeLeft: number;
}

/** Scalars in a shot, in track order. */
export const SHOT_CHANNELS = 12;

/**
 * Flattens a shot into the vector that camera tracks interpolate.
 * @param shot The shot.
 * @returns Twelve numbers.
 */
export function shotToVector(shot: Shot): number[] {
	return [...shot.target, shot.azimuth, shot.elevation, shot.fit, shot.placeX, shot.placeY, shot.roll, shot.fov, shot.focus, shot.aperture];
}

/**
 * How portrait a viewport is, so shots blend continuously instead of switching at a breakpoint.
 * @param aspect Width over height.
 * @returns 0 for landscape, 1 for portrait.
 */
export function tallness(aspect: number): number {
	return 1 - smoothstep(0.72, 1.3, aspect);
}

/**
 * Solves camera numbers from a composition vector and the real viewport.
 *
 * Distance comes from whichever field of view is narrower, so the `fit` sphere stays
 * in frame on any aspect ratio. Safe-area insets shrink the usable frame and shift
 * its centre, which keeps subjects clear of notches and home indicators.
 * @param vector A vector from a camera track.
 * @param viewport The viewport.
 * @returns The solved camera.
 */
export function solveShot(vector: Float64Array, viewport: Viewport): SolvedShot {
	const [tx = 0, ty = 0, tz = 0, azimuth = 0, elevation = 0, fit = 1, placeX = 0, placeY = 0, roll = 0, fov = 30, focus = 1, aperture = 0] = vector;
	const { width, height, safeTop, safeRight, safeBottom, safeLeft } = viewport;
	const usableWidth = Math.max(1, width - safeLeft - safeRight);
	const usableHeight = Math.max(1, height - safeTop - safeBottom);
	const tanVertical = Math.tan((fov * Math.PI) / 360);
	const tanHorizontal = tanVertical * (width / height);
	const limit = Math.min(tanVertical * (usableHeight / height), tanHorizontal * (usableWidth / width));
	const distance = fit / limit;
	const cosElevation = Math.cos(elevation);
	const position: Vec3 = [
		tx + Math.sin(azimuth) * cosElevation * distance,
		ty + Math.sin(elevation) * distance,
		tz + Math.cos(azimuth) * cosElevation * distance,
	];
	return {
		position,
		target: [tx, ty, tz],
		fov,
		roll,
		shiftX: placeX + (safeLeft - safeRight) / width,
		shiftY: placeY + (safeBottom - safeTop) / height,
		focusDistance: distance * focus,
		aperture,
	};
}
