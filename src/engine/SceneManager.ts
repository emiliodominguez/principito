import { Scene, Vector3 } from "three";

import { poseIndex, POSES_PER_SECOND } from "#story/cadence";
import { CHAPTERS } from "#story/chapters";
import { createTrack, layoutChapters, lerp, smoothstep, spanAt, type VectorTrack } from "#story/timeline";
import type { ChapterId, ChapterSpan, LookKey, StageLook } from "#story/types";

import type { Chapter, Stage } from "#chapters/Chapter";

import type { AssetManager } from "./AssetManager";
import { Backdrop } from "./Backdrop";
import { CameraController } from "./CameraController";
import { HangingStars } from "./HangingStars";
import { Lighting } from "./Lighting";
import type { TierSettings } from "./PerformanceManager";
import { createPuppetUniforms, Puppet } from "./Puppet";
import type { Renderer } from "./Renderer";
import type { SolvedShot, Viewport } from "./ResponsiveComposition";

export type ChapterFactory = (span: ChapterSpan, stage: Stage) => Chapter;

const LOOK_SIZE = 11;

/**
 * Flattens a stage look for its track.
 * @param look The look.
 * @returns Its numbers.
 */
function lookToVector(look: StageLook): number[] {
	return [...look.keyColor, look.keyIntensity, ...look.fillColor, look.fillIntensity, look.dusk, look.exposure, look.glow];
}

/**
 * Builds the track of all looks across the story.
 * @param spans The chapter layout.
 * @returns The look track.
 */
function buildLookTrack(spans: readonly ChapterSpan[]): VectorTrack {
	const keys: { time: number; look: StageLook }[] = [];
	CHAPTERS.forEach((chapter, index) => {
		const span = spans[index];
		if (!span) return;
		for (const key of chapter.looks as readonly LookKey[]) keys.push({ time: lerp(span.start, span.end, key.at), look: key.look });
	});
	return createTrack(
		keys.map((key) => key.time),
		keys.map((key) => lookToVector(key.look)),
	);
}

/** Owns the set: everything on stage, and which chapter is directing it. */
export class SceneManager {
	readonly scene = new Scene();
	readonly camera: CameraController;
	readonly spans = layoutChapters(CHAPTERS);
	readonly chapters = new Map<ChapterId, Chapter>();

	private readonly lookTrack = buildLookTrack(this.spans);
	private readonly lookSample = new Float64Array(LOOK_SIZE);
	private readonly lookFocus = new Vector3();
	private readonly viewAxis = new Vector3();
	private readonly chest = new Vector3();
	private progress = 0;
	private backdrop: Backdrop | undefined;
	private lighting: Lighting | undefined;
	private stageInstance: Stage | undefined;
	private readonly pending = new Map<ChapterId, Promise<void>>();
	private readonly uniforms;

	constructor(
		private readonly renderer: Renderer,
		private readonly assets: AssetManager,
		private readonly settings: TierSettings,
		private readonly factories: Readonly<Record<ChapterId, ChapterFactory>>,
	) {
		this.camera = new CameraController(CHAPTERS);
		this.uniforms = createPuppetUniforms();
	}

	/**
	 * Loads what the opening shot needs and builds the shared set.
	 * @returns When the opening can be shown.
	 */
	async prepareStage(): Promise<void> {
		const [princeModel, starsModel, night, dusk] = await Promise.all([
			this.assets.model("prince"),
			this.assets.model("stars"),
			this.assets.painting("universe"),
			this.assets.painting("dusk"),
		]);
		const { scene, settings } = this;
		const shadows = settings.shadowSize > 0;
		this.backdrop = new Backdrop(night, dusk);
		scene.add(this.backdrop.mesh);
		this.lighting = new Lighting(scene, this.renderer.webgl, settings);
		const prince = new Puppet(princeModel, this.uniforms, shadows);
		scene.add(prince.root);
		const stars = new HangingStars(scene, starsModel.scene, settings.hangingStars);
		this.stageInstance = {
			scene,
			settings,
			prince,
			stars,
			lighting: this.lighting,
			uniforms: this.uniforms,
			props: new Map(),
			model: (name) => this.assets.model(name),
			painting: (name) => this.assets.painting(name),
		};
		await this.ensureChapter("universe");
		await this.ensureChapter("planet");
		this.renderer.webgl.shadowMap.autoUpdate = false;
		await this.renderer.prewarm(this.scene, this.camera.camera);
	}

	/**
	 * Creates and prepares a chapter once. Safe to call repeatedly.
	 * @param id The chapter.
	 * @returns When the chapter can appear.
	 */
	ensureChapter(id: ChapterId): Promise<void> {
		const existing = this.pending.get(id);
		if (existing) return existing;
		const stage = this.stageInstance;
		const span = this.spans.find((candidate) => candidate.id === id);
		if (!stage || !span) return Promise.resolve();
		const chapter = this.factories[id](span, stage);
		const work = chapter.prepare().then(async () => {
			// Takes its place at once: a set waiting on the GPU must already be where its chapter wants it
			// for this moment, not sitting at its final mark in full view of whatever is on screen.
			this.chapters.set(id, chapter);
			const t = (this.progress - span.start) / (span.end - span.start);
			chapter.update(t, { seconds: 0, pose: 0, clock: 0, owner: false });
			if (id !== "universe" && id !== "planet") await this.renderer.prewarm(this.scene, this.camera.camera);
			chapter.ready = true;
		});
		this.pending.set(id, work);
		return work;
	}

	/**
	 * Whether a chapter's set has arrived.
	 * @param id The chapter.
	 * @returns True once it can be shown.
	 */
	isReady(id: ChapterId): boolean {
		return this.chapters.get(id)?.ready === true;
	}

	/**
	 * The shared stage, once built.
	 * @returns The stage.
	 */
	stage(): Stage | undefined {
		return this.stageInstance;
	}

	/**
	 * Applies a story position to the whole set.
	 * @param progress Story position.
	 * @param seconds Stage time.
	 * @param viewport The viewport.
	 * @param pointerX Pointer, -1 to 1.
	 * @param pointerY Pointer, -1 to 1.
	 * @returns The solved camera shot.
	 */
	update(progress: number, seconds: number, viewport: Viewport, pointerX: number, pointerY: number): SolvedShot {
		const pose = poseIndex(seconds);
		this.progress = progress;
		const owner = spanAt(this.spans, progress);
		const stage = this.stageInstance;
		const solved = this.camera.update(progress, viewport, pointerX, pointerY);
		for (const chapter of this.chapters.values()) {
			const span = chapter.span;
			const t = (progress - span.start) / (span.end - span.start);
			chapter.update(t, { seconds, pose, clock: seconds * POSES_PER_SECOND, owner: span.id === owner.id });
		}
		if (stage) {
			const flying = owner.id === "journey";
			stage.prince.rig.stopOverlay(flying ? "scarf_flutter" : "scarf_gust");
			stage.prince.rig.overlay(flying ? "scarf_gust" : "scarf_flutter", seconds * POSES_PER_SECOND);
			stage.prince.rig.overlay("face", seconds * POSES_PER_SECOND);
			stage.prince.rig.commit();
			stage.prince.root.updateMatrixWorld(true);
			stage.stars.pose(seconds);
			const opening = this.spans.find((span) => span.id === "rose");
			stage.stars.fadeThreads(opening ? 1 - smoothstep(opening.end - 0.035, opening.end, progress) : 1);
		}
		for (const chapter of this.chapters.values()) {
			const span = chapter.span;
			const t = (progress - span.start) / (span.end - span.start);
			chapter.afterPose(t, { seconds, pose, clock: seconds * POSES_PER_SECOND, owner: span.id === owner.id });
		}
		this.applyLook(progress, solved);
		return { ...solved, focusDistance: this.focusOnPrince(solved.focusDistance) };
	}

	/**
	 * Pulls focus to the Prince, as a focus puller would. He is the subject of every shot, and in
	 * the flight the camera's aim and his position differ enough that a fixed plane would miss him.
	 * @param fallback Focus distance from the shot, used before the stage exists.
	 * @returns Distance from the lens to his chest along the view axis.
	 */
	private focusOnPrince(fallback: number): number {
		const stage = this.stageInstance;
		if (!stage) return fallback;
		const camera = this.camera.camera;
		camera.getWorldDirection(this.viewAxis);
		this.chest.set(0, 1, 0).applyQuaternion(stage.prince.root.quaternion).add(stage.prince.root.position);
		return Math.max(0.5, this.chest.sub(camera.position).dot(this.viewAxis));
	}

	/**
	 * Evaluates the lighting plot.
	 * @param progress Story position.
	 * @param solved The camera shot, which decides where shadows are needed.
	 */
	private applyLook(progress: number, solved: SolvedShot): void {
		const sample = this.lookTrack.sample(progress, this.lookSample);
		const [r0 = 1, g0 = 1, b0 = 1, keyIntensity = 2, r1 = 1, g1 = 1, b1 = 1, fillIntensity = 1, dusk = 0, exposure = 1, glow = 0] = sample;
		const look: StageLook = { keyColor: [r0, g0, b0], keyIntensity, fillColor: [r1, g1, b1], fillIntensity, dusk, exposure, glow };
		this.lookFocus.set(...solved.target);
		const reach =
			Math.hypot(solved.position[0] - solved.target[0], solved.position[1] - solved.target[1], solved.position[2] - solved.target[2]) * 0.33;
		this.lighting?.update(look, this.lookFocus, reach);
		this.camera.camera.getWorldDirection(this.viewAxis);
		this.backdrop?.update(dusk, exposure, this.camera.camera.position, Math.atan2(this.viewAxis.x, -this.viewAxis.z));
	}
}
