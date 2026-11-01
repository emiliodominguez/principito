import { poseNoise } from "./cadence";
import { FLIGHT_PATH, FOX_HILL, PLANET_RADIUS } from "./world";

/** Where one hanging star lives. Plain numbers, so layouts can be tested without a renderer. */
export interface StarPlacement {
	readonly x: number;
	readonly y: number;
	readonly z: number;
	readonly size: number;
	/** Length of thread up to the unseen rail above the set. */
	readonly thread: number;
	readonly tilt: number;
	readonly yaw: number;
	readonly roll: number;
	/** Radians of gentle drift. */
	readonly sway: number;
}

/**
 * Stars composed by hand for the opening shot, in a frame-relative layout measured from the
 * reference: a loose cluster upper left, a few beyond the raised hand, the largest near the fingertip.
 * x and y are in units around the Prince, z is the depth behind him.
 */
const OPENING: ReadonlyArray<readonly [number, number, number, number]> = [
	[1.72, 5.05, -0.5, 0.17],
	[1.06, 5.0, -1.2, 0.07],
	[2.24, 5.32, -1.3, 0.075],
	[2.62, 4.85, -2.2, 0.11],
	[-0.42, 5.2, -2.4, 0.09],
	[-1.22, 5.15, -1.5, 0.08],
	[-1.86, 5.4, -2.6, 0.12],
	[-2.42, 4.92, -1.8, 0.075],
	[-2.5, 3.75, -2, 0.095],
	[-1.86, 4.72, -3, 0.12],
	[-0.46, 4.72, -3, 0.06],
	[1.22, 4.42, -2.2, 0.055],
];

/**
 * Lays out every hanging star: the composed opening, then a seeded scatter around
 * the planet and along the flight path, near enough first so tiers can truncate.
 * @returns The stars in priority order.
 */
function layout(): StarPlacement[] {
	const stars: StarPlacement[] = OPENING.map(([x, y, z, size], index) => ({
		x,
		y,
		z,
		size,
		thread: 70 + poseNoise(index, 5) * 6,
		tilt: (poseNoise(index, 6) - 0.5) * 0.12,
		yaw: (poseNoise(index, 7) - 0.5) * 0.7,
		roll: (poseNoise(index, 8) - 0.5) * 0.14,
		sway: 0.0035 + poseNoise(index, 9) * 0.004,
	}));
	for (let index = 0; index < 120; index++) {
		const salt = index + 100;
		let x: number;
		let y: number;
		let z: number;
		if (index % 2 === 0) {
			const angle = poseNoise(salt, 10) * Math.PI * 2;
			const reach = PLANET_RADIUS + 2.4 + poseNoise(salt, 11) * 9;
			x = Math.cos(angle) * reach;
			z = Math.sin(angle) * reach - 2;
			y = (poseNoise(salt, 12) - 0.42) * 16;
		} else {
			const leg = 1 + Math.floor(poseNoise(salt, 13) * (FLIGHT_PATH.length - 1));
			const a = FLIGHT_PATH[leg - 1] ?? FOX_HILL;
			const b = FLIGHT_PATH[leg] ?? FOX_HILL;
			const t = poseNoise(salt, 14);
			x = a[0] + (b[0] - a[0]) * t + (poseNoise(salt, 15) - 0.5) * 18;
			y = a[1] + (b[1] - a[1]) * t + (poseNoise(salt, 16) - 0.35) * 13;
			z = a[2] + (b[2] - a[2]) * t + (poseNoise(salt, 17) - 0.5) * 16;
		}
		stars.push({
			x,
			y,
			z,
			size: 0.07 + poseNoise(salt, 18) ** 2 * 0.2,
			thread: 18 + poseNoise(salt, 19) * 10,
			tilt: (poseNoise(salt, 20) - 0.5) * 0.4,
			yaw: poseNoise(salt, 21) * Math.PI * 2,
			roll: (poseNoise(salt, 22) - 0.5) * 0.7,
			sway: 0.003 + poseNoise(salt, 23) * 0.004,
		});
	}
	return stars;
}

export const STAR_FIELD: readonly StarPlacement[] = layout();
