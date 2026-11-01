import type { ChapterDefinition, Shot, StageLook, Vec3 } from "./types";
import { FOX_HILL, FOX_HILL_TOP, FOX_LINE_Z, PLANET_RADIUS } from "./world";

/**
 * The film's shot list and lighting plot. All cinematography lives here as data:
 * engine code never contains a camera position.
 */

const TOP = PLANET_RADIUS;
const HILL: Vec3 = [FOX_HILL[0], FOX_HILL[1] + FOX_HILL_TOP - 0.2, FOX_HILL[2] + FOX_LINE_Z];

/**
 * Fills in a shot's usual lens choices.
 * @param partial What this shot specifies.
 * @returns A complete shot.
 */
function shot(partial: Partial<Shot> & Pick<Shot, "target" | "fit">): Shot {
	return { azimuth: 0, elevation: 0.03, placeX: 0, placeY: 0, roll: 0, fov: 22, focus: 1, aperture: 0.05, ...partial };
}

const NIGHT: StageLook = {
	keyColor: [1, 0.92, 0.8],
	keyIntensity: 2.3,
	fillColor: [0.72, 0.88, 0.92],
	fillIntensity: 1.15,
	dusk: 0,
	exposure: 1,
	glow: 0,
};
const INTIMATE: StageLook = { ...NIGHT, keyColor: [1, 0.86, 0.68], keyIntensity: 2, fillIntensity: 0.8, exposure: 0.8, glow: 1 };
const VOYAGE: StageLook = { ...NIGHT, keyColor: [1, 0.95, 0.86], keyIntensity: 2.5, fillIntensity: 1.25, exposure: 1.02 };
const DUSK: StageLook = {
	keyColor: [1, 0.76, 0.5],
	keyIntensity: 2.7,
	fillColor: [0.88, 0.8, 0.72],
	fillIntensity: 1.05,
	dusk: 1,
	exposure: 1.02,
	glow: 0,
};

/** The stage lights nearly out: a day passing on the fox's hill. */
const NIGHTFALL: StageLook = { ...DUSK, keyIntensity: 0.5, fillIntensity: 0.42, exposure: 0.42, dusk: 0.5 };

export const CHAPTERS: readonly ChapterDefinition[] = [
	{
		id: "universe",
		length: 2.6,
		assets: ["prince", "stars", "universe", "dusk"],
		shots: [
			{
				at: 0,
				wide: shot({ target: [0.05, TOP + 1.3, 0], fit: 0.8, azimuth: -0.1, placeX: 0.28, placeY: 0.02, aperture: 0.016 }),
				tall: { target: [0.08, TOP + 1.3, 0], fit: 0.82, placeX: 0, placeY: -0.1, azimuth: -0.06 },
			},
			{
				at: 0.55,
				wide: shot({ target: [0.05, TOP + 1.24, 0], fit: 0.92, azimuth: -0.06, placeX: 0.26, placeY: 0, aperture: 0.016 }),
				tall: { target: [0.08, TOP + 1.2, 0], fit: 0.98, placeX: 0, placeY: -0.12, azimuth: -0.04 },
			},
			{
				at: 1,
				wide: shot({ target: [0, TOP + 0.95, 0], fit: 1.65, azimuth: 0.02, placeX: 0.18, aperture: 0.037 }),
				tall: { fit: 1.45, placeX: 0.03, placeY: -0.12 },
			},
		],
		looks: [{ at: 0, look: NIGHT }],
		beats: [
			{ id: "opening", from: 0.03, to: 0.46, wide: "upper", tall: "top" },
			{ id: "remember", from: 0.52, to: 0.92, wide: "upper", tall: "top" },
		],
		hotspots: [],
	},
	{
		id: "planet",
		length: 3.2,
		assets: ["asteroid"],
		shots: [
			{
				at: 0.34,
				wide: shot({ target: [0, TOP * 0.5, 0], fit: 3.7, azimuth: 0.12, elevation: 0.1, placeX: 0.2, aperture: 0.056 }),
				tall: { fit: 3.6, placeX: 0, placeY: -0.18 },
			},
			{
				at: 0.72,
				wide: shot({ target: [0, TOP * 0.25, 0], fit: 4.55, azimuth: 0.72, elevation: 0.22, placeX: -0.2, aperture: 0.056 }),
				tall: { fit: 4.3, placeX: 0, placeY: -0.2 },
			},
			{
				at: 1,
				wide: shot({ target: [0.2, TOP * 0.56, 0], fit: 3.6, azimuth: 0.3, elevation: 0.16, placeX: -0.17, aperture: 0.066 }),
				tall: { fit: 3.5, placeX: 0, placeY: -0.2 },
			},
		],
		looks: [{ at: 0.2, look: NIGHT }],
		beats: [
			{ id: "small", from: 0.24, to: 0.56, wide: "left", tall: "top" },
			{ id: "chores", from: 0.62, to: 0.93, wide: "right", tall: "top" },
		],
		hotspots: [],
	},
	{
		id: "rose",
		length: 3.4,
		assets: ["rose"],
		shots: [
			{
				at: 0.3,
				wide: shot({ target: [0.5, TOP + 0.6, 0.1], fit: 1.7, azimuth: 0.1, elevation: 0.1, placeX: 0.22, aperture: 0.094 }),
				tall: { fit: 1.45, placeX: 0, placeY: -0.2 },
			},
			{
				at: 0.66,
				wide: shot({ target: [0.62, TOP + 0.34, 0.1], fit: 1.22, azimuth: 0.05, elevation: 0.08, placeX: 0.26, aperture: 0.05 }),
				tall: { fit: 1, placeX: 0, placeY: -0.22 },
			},
			{
				at: 1,
				wide: shot({ target: [0.62, TOP + 0.5, 0.1], fit: 1.5, azimuth: -0.08, elevation: 0.12, placeX: 0, placeY: -0.24, aperture: 0.094 }),
				tall: { fit: 1.14, placeX: 0, placeY: -0.22 },
			},
		],
		looks: [
			{ at: 0.18, look: NIGHT },
			{ at: 0.55, look: INTIMATE },
			{ at: 1, look: INTIMATE },
		],
		beats: [
			{ id: "arrival", from: 0.08, to: 0.36, wide: "left", tall: "top" },
			{ id: "care", from: 0.42, to: 0.68, wide: "left", tall: "top" },
			{ id: "yours", from: 0.72, to: 0.96, wide: "top", tall: "top" },
		],
		hotspots: [{ id: "rose", from: 0.4, to: 0.96 }],
	},
	{
		id: "journey",
		length: 4,
		assets: ["birds", "paper_planets", "cloud_a", "cloud_b", "cloud_c"],
		shots: [
			{
				at: 0.14,
				wide: shot({ target: [0.5, TOP + 1.7, 0], fit: 2.6, azimuth: 0.3, elevation: -0.04, placeX: 0.1, aperture: 0.094 }),
				tall: { fit: 2.3, placeX: 0, placeY: -0.16 },
			},
			{
				at: 0.34,
				wide: shot({ target: [3.4, 9.5, -6.2], fit: 2.5, azimuth: 0.93, elevation: -0.03, placeX: -0.2, aperture: 0.075, fov: 26 }),
				tall: { fit: 2.8, placeX: 0, placeY: -0.16 },
			},
			{
				at: 0.62,
				wide: shot({ target: [14.6, 6.8, -24.6], fit: 2.5, azimuth: 0.93, elevation: -0.02, placeX: -0.2, aperture: 0.084, fov: 30 }),
				tall: { fit: 2.7, placeX: 0, placeY: -0.16 },
			},
			{
				at: 0.86,
				wide: shot({ target: [22.5, 1, -39.3], fit: 2.7, azimuth: 0.7, elevation: 0.03, placeX: -0.18, aperture: 0.084, fov: 30 }),
				tall: { fit: 2.9, placeX: 0, placeY: -0.16 },
			},
			{
				at: 1,
				wide: shot({ target: [25, -2.8, -44], fit: 3.6, azimuth: 0.1, elevation: 0.12, aperture: 0.075, fov: 28 }),
				tall: { fit: 3.4, placeY: -0.1 },
			},
		],
		looks: [
			{ at: 0.1, look: INTIMATE },
			{ at: 0.3, look: VOYAGE },
			{ at: 0.84, look: VOYAGE },
			{ at: 1, look: { ...VOYAGE, dusk: 0.55 } },
		],
		beats: [
			{ id: "leave", from: 0.05, to: 0.27, wide: "left", tall: "top" },
			{ id: "wind", from: 0.32, to: 0.54, wide: "right", tall: "top" },
			{ id: "planets", from: 0.62, to: 0.86, wide: "right", tall: "top" },
		],
		hotspots: [],
	},
	{
		id: "fox",
		length: 3.8,
		assets: ["fox", "fox_hill"],
		shots: [
			{
				at: 0.14,
				wide: shot({
					target: [HILL[0] + 0.5, HILL[1] + 0.55, HILL[2]],
					fit: 2.5,
					azimuth: -0.16,
					elevation: 0.16,
					placeX: 0.18,
					aperture: 0.066,
				}),
				tall: { fit: 2.7, placeX: 0, placeY: -0.14 },
			},
			{
				at: 0.55,
				wide: shot({
					target: [HILL[0] + 0.1, HILL[1] + 0.72, HILL[2]],
					fit: 1.8,
					azimuth: -0.1,
					elevation: 0.14,
					placeX: -0.05,
					placeY: -0.2,
					aperture: 0.094,
				}),
				tall: { fit: 1.55, placeX: 0, placeY: -0.2 },
			},
			{
				at: 1,
				wide: shot({
					target: [HILL[0] - 0.05, HILL[1] + 0.72, HILL[2]],
					fit: 1.5,
					azimuth: 0.04,
					elevation: 0.1,
					placeX: 0,
					placeY: -0.24,
					aperture: 0.094,
				}),
				tall: { fit: 1.4, placeY: -0.2 },
			},
		],
		looks: [
			{ at: 0.12, look: DUSK },
			{ at: 0.4, look: DUSK },
			{ at: 0.46, look: NIGHTFALL },
			{ at: 0.52, look: DUSK },
			{ at: 0.58, look: NIGHTFALL },
			{ at: 0.64, look: DUSK },
			{ at: 1, look: { ...DUSK, keyIntensity: 2.4, exposure: 0.94 } },
		],
		beats: [
			{ id: "waiting", from: 0.07, to: 0.34, wide: "top", tall: "top" },
			{ id: "closer", from: 0.4, to: 0.64, wide: "top", tall: "top" },
			{ id: "silence", from: 0.76, to: 0.97, wide: "top", tall: "top" },
		],
		hotspots: [],
	},
	{
		id: "finale",
		length: 4.4,
		assets: [],
		shots: [
			{
				at: 0.26,
				wide: shot({ target: [HILL[0], HILL[1] + 1, HILL[2]], fit: 3, azimuth: 0.02, elevation: -0.12, aperture: 0.03 }),
				tall: { fit: 2.6, placeY: -0.2 },
			},
			{
				at: 0.58,
				wide: shot({ target: [HILL[0], HILL[1] + 4.5, HILL[2]], fit: 8.5, azimuth: -0.06, elevation: -0.1, aperture: 0.016 }),
				tall: { fit: 6.2, placeY: -0.16 },
			},
			{
				at: 0.8,
				wide: shot({ target: [HILL[0], HILL[1] + 16, HILL[2]], fit: 11, azimuth: -0.08, elevation: -0.1, aperture: 0.024, fov: 26 }),
				tall: { fit: 8.6, placeY: 0 },
			},
			{
				at: 1,
				wide: shot({ target: [HILL[0], HILL[1] + 34, HILL[2]], fit: 14, azimuth: -0.1, elevation: -0.1, aperture: 0.03, fov: 26 }),
				tall: { fit: 10, placeY: 0 },
			},
		],
		looks: [
			{ at: 0.05, look: { ...DUSK, keyIntensity: 2.4, exposure: 0.94 } },
			{ at: 0.36, look: { ...NIGHT, dusk: 0.2, exposure: 0.6 } },
			{ at: 0.66, look: { ...NIGHT, exposure: 0.34 } },
			{ at: 1, look: { ...NIGHT, keyIntensity: 2.8, exposure: 0.2 } },
		],
		beats: [
			{ id: "distance", from: 0.06, to: 0.28, wide: "left", tall: "top" },
			{ id: "unseen", from: 0.33, to: 0.55, wide: "center", tall: "center", night: true },
			{ id: "look", from: 0.6, to: 0.84, wide: "center", tall: "center", night: true },
		],
		hotspots: [{ id: "stars", from: 0.64, to: 0.84 }],
	},
];
