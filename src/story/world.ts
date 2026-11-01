import type { Vec3 } from "./types";

/** Radius of the Prince's asteroid in set units; he stands 1.72 tall on it. */
export const PLANET_RADIUS = 3.2;

/** Angle from the planet's crown, toward +X, at which the rose grows. */
export const ROSE_ANGLE = 0.86;

/** Angle along the planet at which the Prince stops walking and kneels. */
export const WALK_END_ANGLE = 0.5;

/** Both characters stand on this line across the hill, forward of its crest so the lens sees their feet. */
export const FOX_LINE_Z = 1.25;

/** The hill where the fox waits, far along the journey. */
export const FOX_HILL: Vec3 = [26, -7, -46];

/** Height of the walkable top of the fox's hill above its origin. */
export const FOX_HILL_TOP = 1.72;

/** World positions the Prince drifts through on his way to the hill. */
export const FLIGHT_PATH: readonly Vec3[] = [
	[0.0, PLANET_RADIUS, 0.0],
	[1.6, 7.6, -3.0],
	[7.5, 8.2, -13.0],
	[15.5, 4.8, -26.0],
	[22.0, 0.4, -38.0],
	[FOX_HILL[0] - 0.82, FOX_HILL[1] + FOX_HILL_TOP - 0.1, FOX_HILL[2] + FOX_LINE_Z],
];
