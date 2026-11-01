import { PerspectiveCamera, Vector3 } from "three";

import { lerp } from "#story/timeline";
import { layoutChapters, createTrack, type VectorTrack } from "#story/timeline";
import type { ChapterDefinition, Shot } from "#story/types";

import { SHOT_CHANNELS, shotToVector, type SolvedShot, solveShot, tallness, type Viewport } from "./ResponsiveComposition";

/** How far the pointer may nudge the lens, as a share of the framed subject. */
const PARALLAX = 0.028;

/**
 * Turns story progress into a camera. Tracks are built once from chapter data, so
 * the camera is a pure function of scroll position and viewport.
 */
export class CameraController {
	readonly camera = new PerspectiveCamera(30, 1, 0.1, 900);

	private readonly wide: VectorTrack;
	private readonly tall: VectorTrack;
	private readonly wideSample = new Float64Array(SHOT_CHANNELS);
	private readonly tallSample = new Float64Array(SHOT_CHANNELS);
	private readonly blended = new Float64Array(SHOT_CHANNELS);
	private readonly lookTarget = new Vector3();
	private solved: SolvedShot | undefined;

	constructor(chapters: readonly ChapterDefinition[]) {
		const spans = layoutChapters(chapters);
		const times: number[] = [];
		const wide: number[][] = [];
		const tall: number[][] = [];
		chapters.forEach((chapter, chapterIndex) => {
			const span = spans[chapterIndex];
			if (!span) return;
			for (const key of chapter.shots) {
				times.push(lerp(span.start, span.end, key.at));
				const merged: Shot = { ...key.wide, ...key.tall };
				wide.push(shotToVector(key.wide));
				tall.push(shotToVector(merged));
			}
		});
		this.wide = createTrack(times, wide);
		this.tall = createTrack(times, tall);
		this.camera.matrixAutoUpdate = true;
	}

	/**
	 * Places the camera for a story position.
	 * @param progress Story position, 0 to 1.
	 * @param viewport The current viewport.
	 * @param pointerX Pointer position, -1 to 1.
	 * @param pointerY Pointer position, -1 to 1.
	 * @returns The solved shot, for depth of field and shadow focus.
	 */
	update(progress: number, viewport: Viewport, pointerX: number, pointerY: number): SolvedShot {
		this.wide.sample(progress, this.wideSample);
		this.tall.sample(progress, this.tallSample);
		const blend = tallness(viewport.width / viewport.height);
		for (let i = 0; i < SHOT_CHANNELS; i++) {
			this.blended[i] = lerp(this.wideSample[i] ?? 0, this.tallSample[i] ?? 0, blend);
		}
		const solved = solveShot(this.blended, viewport);
		this.solved = solved;
		const camera = this.camera;
		const fit = this.blended[5] ?? 1;
		camera.fov = solved.fov;
		camera.aspect = viewport.width / viewport.height;
		this.lookTarget.set(...solved.target);
		camera.position.set(...solved.position);
		camera.up.set(Math.sin(solved.roll), Math.cos(solved.roll), 0);
		camera.lookAt(this.lookTarget);
		camera.translateX(pointerX * fit * PARALLAX);
		camera.translateY(-pointerY * fit * PARALLAX * 0.6);
		camera.updateProjectionMatrix();
		// Lens shift: slides the image on the sensor, so the subject moves off-centre with no keystone tilt.
		const elements = camera.projectionMatrix.elements;
		elements[8] = -solved.shiftX;
		elements[9] = -solved.shiftY;
		camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
		return solved;
	}

	/**
	 * The last solved shot.
	 * @returns The shot, if one has been solved.
	 */
	current(): SolvedShot | undefined {
		return this.solved;
	}
}
