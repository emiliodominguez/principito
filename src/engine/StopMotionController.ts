import { type AnimationAction, type AnimationClip, AnimationMixer, InterpolateDiscrete, InterpolateLinear, LoopRepeat, type Object3D } from "three";

import { POSES_PER_SECOND, poseIndex } from "#story/cadence";

/**
 * A puppet's animation, driven by explicit frame positions rather than accumulated time.
 *
 * The body plays one clip at a time, chosen by the story; overlay clips (scarf, eyes)
 * touch only their own bones and run alongside it. Frames may be fractional. The same
 * request always produces the same pose, so scrubbing backward through the story
 * cannot corrupt anything.
 */
export class PuppetRig {
	private readonly mixer: AnimationMixer;
	private readonly actions = new Map<string, AnimationAction>();
	private body: AnimationAction | undefined;
	private dirty = true;
	private readonly requested = new Map<string, number>();

	constructor(root: Object3D, clips: readonly AnimationClip[]) {
		this.mixer = new AnimationMixer(root);
		for (const clip of clips) {
			// Motion glides between frames. Replacement parts (eyes, mouths, hands) are swapped, so they must snap.
			for (const track of clip.tracks) track.setInterpolation(track.name.startsWith("fx") ? InterpolateDiscrete : InterpolateLinear);
			const action = this.mixer.clipAction(clip);
			action.setLoop(LoopRepeat, Infinity);
			action.clampWhenFinished = true;
			action.paused = true;
			this.actions.set(clip.name, action);
		}
	}

	/**
	 * Sets the body clip and frame.
	 * @param clip Clip name.
	 * @param frame Frame position within the clip.
	 */
	pose(clip: string, frame: number): void {
		const action = this.actions.get(clip);
		if (!action) return;
		if (this.body !== action) {
			if (this.body) {
				this.body.stop();
				this.body.enabled = false;
			}
			action.enabled = true;
			action.play();
			action.paused = true;
			this.body = action;
			this.dirty = true;
			// Stopping rewound this action, so what it last showed no longer holds.
			this.requested.delete(clip);
		}
		this.seek(clip, action, frame);
	}

	/**
	 * Sets an overlay clip's frame, starting it if needed.
	 * @param clip Clip name.
	 * @param frame Frame position; wraps around the clip.
	 */
	overlay(clip: string, frame: number): void {
		const action = this.actions.get(clip);
		if (!action) return;
		if (!action.isRunning() && !action.enabled) action.enabled = true;
		if (!this.requested.has(clip)) {
			action.play();
			action.paused = true;
		}
		const length = Math.max(1, poseIndex(action.getClip().duration));
		this.seek(clip, action, ((frame % length) + length) % length);
	}

	/**
	 * Stops an overlay clip.
	 * @param clip Clip name.
	 */
	stopOverlay(clip: string): void {
		const action = this.actions.get(clip);
		if (!action || !this.requested.has(clip)) return;
		action.stop();
		this.requested.delete(clip);
		this.dirty = true;
	}

	/**
	 * Writes pending pose changes into the skeleton.
	 * @returns Whether anything changed.
	 */
	commit(): boolean {
		if (!this.dirty) return false;
		this.mixer.update(0);
		this.dirty = false;
		return true;
	}

	/** Frees the mixer's cached bindings. */
	dispose(): void {
		this.mixer.stopAllAction();
		this.mixer.uncacheRoot(this.mixer.getRoot());
	}

	/**
	 * Moves an action to a frame if it is not already there.
	 * @param clip Clip name.
	 * @param action The action.
	 * @param frame Frame position.
	 */
	private seek(clip: string, action: AnimationAction, frame: number): void {
		if (this.requested.get(clip) === frame) return;
		this.requested.set(clip, frame);
		action.time = Math.min(frame / POSES_PER_SECOND, action.getClip().duration);
		this.dirty = true;
	}
}
