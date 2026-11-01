import { AsteroidChapter } from "#chapters/AsteroidChapter";
import type { Chapter, Stage } from "#chapters/Chapter";
import { FinaleChapter } from "#chapters/FinaleChapter";
import { FoxChapter } from "#chapters/FoxChapter";
import { JourneyChapter } from "#chapters/JourneyChapter";
import { RoseChapter } from "#chapters/RoseChapter";
import { UniverseChapter } from "#chapters/UniverseChapter";
import { CHAPTERS } from "#story/chapters";
import { spanAt } from "#story/timeline";
import type { ChapterDefinition, ChapterId, ChapterSpan } from "#story/types";

import { AssetManager } from "./AssetManager";
import { AudioDirector } from "./AudioDirector";
import { InteractionManager } from "./InteractionManager";
import { classifyDevice, PerformanceManager, settingsFor, type Tier, type TierSettings } from "./PerformanceManager";
import { Renderer } from "./Renderer";
import type { Viewport } from "./ResponsiveComposition";
import { type ChapterFactory, SceneManager } from "./SceneManager";
import { ScrollDirector } from "./ScrollDirector";
import { StoryOverlay } from "./StoryOverlay";

/**
 * Wraps a chapter class with its definition.
 * @param id The chapter.
 * @param create Builds the chapter.
 * @returns A factory for the scene manager.
 */
function factory(id: ChapterId, create: (definition: ChapterDefinition, span: ChapterSpan, stage: Stage) => Chapter): ChapterFactory {
	const definition = CHAPTERS.find((chapter) => chapter.id === id);
	if (!definition) throw new Error(`unknown chapter ${id}`);
	return (span, stage) => create(definition, span, stage);
}

const FACTORIES: Readonly<Record<ChapterId, ChapterFactory>> = {
	universe: factory("universe", (d, s, stage) => new UniverseChapter(d, s, stage)),
	planet: factory("planet", (d, s, stage) => new AsteroidChapter(d, s, stage)),
	rose: factory("rose", (d, s, stage) => new RoseChapter(d, s, stage)),
	journey: factory("journey", (d, s, stage) => new JourneyChapter(d, s, stage)),
	fox: factory("fox", (d, s, stage) => new FoxChapter(d, s, stage)),
	finale: factory("finale", (d, s, stage) => new FinaleChapter(d, s, stage)),
};

/**
 * Reads the renderer's identity, which is hidden behind an extension on most browsers.
 * @param gl The context.
 * @returns The GPU name, if available.
 */
function gpuName(gl: WebGL2RenderingContext): string {
	const debug = gl.getExtension("WEBGL_debug_renderer_info");
	return String(gl.getParameter(debug ? debug.UNMASKED_RENDERER_WEBGL : gl.RENDERER));
}

/**
 * Works out the performance tier, honouring a ?tier= override used for testing.
 * @param canvas The story canvas.
 * @returns The tier.
 */
function chooseTier(canvas: HTMLCanvasElement): Tier {
	const override = new URLSearchParams(location.search).get("tier");
	if (override === "high" || override === "medium" || override === "low") return override;
	const gl = canvas.getContext("webgl2");
	if (!gl) return "low";
	const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
	return classifyDevice({
		renderer: gpuName(gl),
		maxTextureSize: Number(gl.getParameter(gl.MAX_TEXTURE_SIZE)),
		deviceMemory: memory,
		cores: navigator.hardwareConcurrency || 4,
		coarsePointer: matchMedia("(pointer: coarse)").matches,
	});
}

/**
 * Measures the safe-area insets, which CSS knows and JavaScript does not.
 * @param probe An element whose padding is the safe area.
 * @returns The viewport.
 */
function readViewport(probe: HTMLElement): Viewport {
	const style = getComputedStyle(probe);
	return {
		width: window.innerWidth,
		height: window.innerHeight,
		safeTop: Number.parseFloat(style.paddingTop) || 0,
		safeRight: Number.parseFloat(style.paddingRight) || 0,
		safeBottom: Number.parseFloat(style.paddingBottom) || 0,
		safeLeft: Number.parseFloat(style.paddingLeft) || 0,
	};
}

/** The running experience: one render loop tying scroll, stage, sound and page together. */
export class StoryApp {
	private readonly renderer: Renderer;
	private readonly assets: AssetManager;
	private readonly performance = new PerformanceManager();
	private readonly manager: SceneManager;
	private readonly director: ScrollDirector;
	private readonly overlay: StoryOverlay;
	private readonly interaction: InteractionManager;
	private readonly audio = new AudioDirector();
	private readonly settings: TierSettings;
	private viewport: Viewport;
	private lastProgress = -1;
	private needsResize = true;
	private fixedSeconds: number | undefined;

	constructor(
		private readonly root: HTMLElement,
		private readonly canvas: HTMLCanvasElement,
		private readonly probe: HTMLElement,
		track: HTMLElement,
	) {
		const tier = chooseTier(canvas);
		this.settings = settingsFor(tier);
		root.dataset["tier"] = tier;
		this.viewport = readViewport(probe);
		this.renderer = new Renderer(canvas, this.settings);
		this.assets = new AssetManager(this.renderer.webgl, tier);
		this.manager = new SceneManager(this.renderer, this.assets, this.settings, FACTORIES);
		this.director = new ScrollDirector(track, false);
		this.overlay = new StoryOverlay(root, CHAPTERS, this.manager.spans);
		this.interaction = new InteractionManager(root, this.manager, this.audio, this.settings.parallax);
		this.performance.onChange((scale) => this.renderer.setScale(scale));
		this.bindPage();
	}

	/**
	 * Loads the opening, shows it and starts the loop.
	 * @param onProgress Receives loading progress, 0 to 1.
	 */
	async start(onProgress: (share: number) => void): Promise<void> {
		this.assets.onProgress(onProgress);
		await this.manager.prepareStage();
		requestAnimationFrame((now) => this.tick(now));
		this.preloadAround(0);
		if (new URLSearchParams(location.search).has("debug")) this.exposeDebugHandle();
	}

	/**
	 * One display frame. The set is always gently moving, so every frame is drawn.
	 * @param now rAF timestamp.
	 */
	private tick(now: number): void {
		requestAnimationFrame((time) => this.tick(time));
		const seconds = this.fixedSeconds ?? now / 1000;
		const pose = Math.floor(seconds * 12);
		const progress = this.director.progress;
		const pointer = this.interaction.ease();
		const scrolled = Math.abs(progress - this.lastProgress) > 1e-7;
		if (this.needsResize) this.applyResize();
		const span = spanAt(this.manager.spans, progress);
		this.root.dataset["waiting"] = this.manager.isReady(span.id) ? "false" : "true";
		if (scrolled) {
			this.overlay.update(progress, span.index);
			this.root.dataset["ended"] = progress > 0.992 ? "true" : "false";
			this.preloadAround(span.index);
			this.audio.setChapter(span.id);
		}
		const solved = this.manager.update(progress, seconds, this.viewport, pointer.x, pointer.y);
		this.interaction.update(progress, this.viewport, seconds);
		this.renderer.webgl.shadowMap.needsUpdate = true;
		this.renderer.render(this.manager.scene, this.manager.camera.camera, pose, solved.focusDistance, solved.aperture);
		this.performance.frame(now);
		this.lastProgress = progress;
	}

	/**
	 * Starts loading the current chapter and the next two, so a set is ready before the camera arrives.
	 * @param index The chapter on stage.
	 */
	private preloadAround(index: number): void {
		for (const offset of [0, 1, 2]) {
			const chapter = CHAPTERS[index + offset];
			if (chapter) void this.manager.ensureChapter(chapter.id);
		}
	}

	/** Connects the page's resize and navigation events. */
	private bindPage(): void {
		const observer = new ResizeObserver(() => {
			this.needsResize = true;
		});
		observer.observe(this.probe);
		window.addEventListener("orientationchange", () => {
			this.needsResize = true;
		});
		for (const link of this.root.querySelectorAll<HTMLElement>("[data-chapter-link]")) {
			link.addEventListener("click", (event) => {
				event.preventDefault();
				const index = Number(link.dataset["chapterLink"]);
				const span = this.manager.spans[index];
				if (!span) return;
				void this.manager.ensureChapter(span.id);
				this.director.seek(span.start + (span.end - span.start) * 0.12);
			});
		}
		this.root.querySelector<HTMLElement>("[data-restart]")?.addEventListener("click", () => this.director.seek(0));
		const sound = this.root.querySelector<HTMLButtonElement>("[data-sound]");
		sound?.addEventListener("click", () => {
			const enabled = this.audio.toggle();
			sound.setAttribute("aria-pressed", String(enabled));
			sound.setAttribute("aria-label", (enabled ? sound.dataset["labelOff"] : sound.dataset["labelOn"]) ?? "");
		});
	}

	/** Resizes everything to the current viewport. */
	private applyResize(): void {
		this.needsResize = false;
		this.viewport = readViewport(this.probe);
		this.renderer.resize(this.viewport.width, this.viewport.height);
		this.canvas.style.width = `${this.viewport.width}px`;
		this.canvas.style.height = `${this.viewport.height}px`;
	}

	/**
	 * Times complete frames at story positions, waiting for the GPU to finish each one.
	 * @param positions Story positions.
	 * @returns Milliseconds per position, plus the drawing buffer size.
	 */
	private timeFrames(positions: readonly number[]): { pixels: string; ms: Record<string, number> } {
		const gl = this.renderer.webgl.getContext();
		const pixel = new Uint8Array(4);
		const ms: Record<string, number> = {};
		for (const position of positions) {
			const samples: number[] = [];
			for (let i = 0; i < 12; i++) {
				const start = performance.now();
				const solved = this.manager.update(position, 2 + i / 12, this.viewport, 0, 0);
				this.renderer.webgl.shadowMap.needsUpdate = true;
				this.renderer.render(this.manager.scene, this.manager.camera.camera, i, solved.focusDistance, solved.aperture);
				gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
				samples.push(performance.now() - start);
			}
			samples.sort((a, b) => a - b);
			ms[String(position)] = Math.round(samples[6] ?? 0);
		}
		return { pixels: this.canvas.width + "x" + this.canvas.height, ms };
	}

	/** Lets tests and capture scripts hold the story at an exact moment. */
	private exposeDebugHandle(): void {
		Object.assign(window, {
			__story: {
				seek: (progress: number, seconds = 1) => {
					this.fixedSeconds = seconds;
					this.director.seek(progress, true);
				},
				spans: this.manager.spans,
				probe: (positions: readonly number[]) => this.timeFrames(positions),
				progress: () => this.director.progress,
				gpu: () => gpuName(this.renderer.webgl.getContext() as WebGL2RenderingContext),
				stage: () => this.manager.stage(),
				ready: (id: ChapterId) => this.manager.ensureChapter(id),
				stats: () => ({
					...this.performance.stats(),
					tier: this.settings.tier,
					calls: this.renderer.webgl.info.render.calls,
					triangles: this.renderer.webgl.info.render.triangles,
					textures: this.renderer.webgl.info.memory.textures,
					geometries: this.renderer.webgl.info.memory.geometries,
				}),
			},
		});
	}
}
