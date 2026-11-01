/**
 * Animation time. Clips are authored at 12 frames per second and glide between frames at
 * display rate. Replacement parts and the birds' wingbeats still step on the pose grid.
 */

export const POSES_PER_SECOND = 12;

/**
 * The 12 fps pose index for a moment in time.
 * @param seconds Time in seconds.
 * @returns The whole pose number.
 */
export function poseIndex(seconds: number): number {
	return Math.floor(seconds * POSES_PER_SECOND + 1e-6);
}

/**
 * The frame position of a one-shot clip at a progress through it. Scroll-driven motion uses
 * this instead of time, so scrubbing backward lands on exactly the same pose.
 * @param progress Progress through the clip, 0 to 1.
 * @param frames The clip's length in frames.
 * @returns The frame position, which may be fractional.
 */
export function frameAtProgress(progress: number, frames: number): number {
	return Math.min(1, Math.max(0, progress)) * frames;
}

/**
 * The frame position in a cycle driven by a travelled distance, so a walk's feet are tied to
 * scroll rather than to the clock.
 * @param distance Accumulated cycle count, may be fractional.
 * @param frames The cycle's length in frames.
 * @returns The frame position.
 */
export function frameInCycle(distance: number, frames: number): number {
	return (distance - Math.floor(distance)) * frames;
}

/**
 * A repeatable pseudo-random value for a pose number. The same pose always gets the same value.
 * @param index Pose number.
 * @param salt Separates independent streams.
 * @returns A value from 0 to 1.
 */
export function poseNoise(index: number, salt = 0): number {
	const value = Math.sin(index * 12.9898 + salt * 78.233) * 43758.5453;
	return value - Math.floor(value);
}
