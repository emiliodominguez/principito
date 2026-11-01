/**
 * The story's domain model. Nothing here knows about Three.js: a chapter is plain
 * data describing what should be true at each moment of the timeline.
 */

export type Vec3 = readonly [number, number, number];
export type Rgb = readonly [number, number, number];

export type ChapterId = "universe" | "planet" | "rose" | "journey" | "fox" | "finale";

/** One camera composition, expressed in terms of what must be seen rather than where the camera is. */
export interface Shot {
	/** World point the lens aims at. */
	readonly target: Vec3;
	/** Radians around the target; 0 looks along -Z from in front of the set. */
	readonly azimuth: number;
	/** Radians above the target. */
	readonly elevation: number;
	/** World radius that must stay in frame, whatever the viewport. Distance is solved from this. */
	readonly fit: number;
	/** Lens shift in screen halves, moving the subject off-centre without rotating the camera. */
	readonly placeX: number;
	readonly placeY: number;
	/** Radians of dutch tilt. */
	readonly roll: number;
	/** Vertical field of view in degrees. */
	readonly fov: number;
	/** Distance in front of the lens, relative to the solved distance, that sits in sharp focus. */
	readonly focus: number;
	/** Strength of the miniature's shallow depth of field. */
	readonly aperture: number;
}

/** A shot authored for wide screens, with whatever a portrait screen needs changed. */
export interface ShotKey {
	/** Position within the chapter, 0 to 1. */
	readonly at: number;
	readonly wide: Shot;
	readonly tall?: Partial<Shot>;
}

/** The lighting and backdrop state of the set. */
export interface StageLook {
	readonly keyColor: Rgb;
	readonly keyIntensity: number;
	readonly fillColor: Rgb;
	readonly fillIntensity: number;
	/** Backdrop painting crossfade: 0 night sky, 1 dusk. */
	readonly dusk: number;
	/** Backdrop brightness. */
	readonly exposure: number;
	/** Warm lamp from below, used intimately in the rose chapter. */
	readonly glow: number;
}

export interface LookKey {
	readonly at: number;
	readonly look: StageLook;
}

export type TextAnchor = "left" | "upper" | "right" | "center" | "top" | "bottom";

/** A line of narration visible over part of a chapter. Copy lives in the i18n catalogues. */
export interface Beat {
	readonly id: string;
	readonly from: number;
	readonly to: number;
	readonly wide: TextAnchor;
	readonly tall: TextAnchor;
	/** Set directly on the night sky in white, without a paper slip. */
	readonly night?: boolean;
}

/** A place on the set the reader can touch. Positions come from the chapter at runtime. */
export interface HotspotDefinition {
	readonly id: string;
	readonly from: number;
	readonly to: number;
}

export interface ChapterDefinition {
	readonly id: ChapterId;
	/** Scroll length in viewport heights. */
	readonly length: number;
	readonly shots: readonly ShotKey[];
	readonly looks: readonly LookKey[];
	readonly beats: readonly Beat[];
	readonly hotspots: readonly HotspotDefinition[];
	/** Asset files the chapter needs loaded before it can appear. */
	readonly assets: readonly string[];
}

export interface ChapterSpan {
	readonly id: ChapterId;
	readonly index: number;
	readonly start: number;
	readonly end: number;
}
