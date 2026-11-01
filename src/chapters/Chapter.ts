import type { Scene, Texture, Vector3 } from "three";
import type { GLTF } from "three/addons/loaders/GLTFLoader.js";

import type { ChapterDefinition, ChapterSpan } from "#story/types";
import type { PuppetUniforms } from "#shaders/puppet";

import type { HangingStars } from "#engine/HangingStars";
import type { Lighting } from "#engine/Lighting";
import type { TierSettings } from "#engine/PerformanceManager";
import type { Puppet } from "#engine/Puppet";

/** What the stage lends a chapter. Chapters never reach for the renderer or the DOM. */
export interface Stage {
	readonly scene: Scene;
	readonly settings: TierSettings;
	readonly prince: Puppet;
	readonly stars: HangingStars;
	readonly lighting: Lighting;
	readonly uniforms: PuppetUniforms;
	/** Shared props other chapters need to see, such as the planet. */
	readonly props: Map<string, unknown>;
	model(name: string): Promise<GLTF>;
	painting(name: string): Promise<Texture>;
}

/** The moment being drawn. Every value is deterministic for a given scroll position and pose. */
export interface Moment {
	readonly seconds: number;
	readonly pose: number;
	/** Continuous animation position in 12 fps frames, for clips that loop with time. */
	readonly clock: number;
	/** Whether this chapter owns the current position. Only the owner directs the Prince. */
	readonly owner: boolean;
}

/** A world point the reader can touch, reported each frame. */
export interface HotspotPlacement {
	readonly id: string;
	readonly position: Vector3;
}

/** A self-contained part of the story. `update` is a pure function of `t` and the moment. */
export abstract class Chapter {
	/** True once `prepare` has finished. */
	ready = false;

	constructor(
		readonly definition: ChapterDefinition,
		readonly span: ChapterSpan,
		protected readonly stage: Stage,
	) {}

	/** Loads assets and builds the chapter's part of the set. */
	abstract prepare(): Promise<void>;

	/**
	 * Applies the chapter's state.
	 * @param t Position in this chapter. May lie outside 0 to 1, so sets can stay on stage for neighbouring chapters.
	 * @param moment The moment being drawn.
	 */
	abstract update(t: number, moment: Moment): void;

	/**
	 * Runs after every puppet has taken its pose, for anything attached to a posed bone.
	 * Reading a bone during `update` would see the previous frame, which depends on the
	 * direction of travel and would break the guarantee that position alone decides the picture.
	 * @param t Chapter position.
	 * @param moment The moment being drawn.
	 */
	afterPose(t: number, moment: Moment): void {
		void t;
		void moment;
	}

	/**
	 * Reports where a hotspot sits.
	 * @param id The hotspot.
	 * @returns Its world position, if it has one right now.
	 */
	hotspot(id: string): Vector3 | undefined {
		void id;
		return undefined;
	}

	/**
	 * Responds to the reader touching a hotspot.
	 * @param id The hotspot.
	 * @param seconds The time of the touch.
	 */
	activate(id: string, seconds: number): void {
		void id;
		void seconds;
	}
}
