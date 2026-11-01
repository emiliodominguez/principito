import type { Camera } from "three";
import {
	DepthTexture,
	HalfFloatType,
	LinearFilter,
	type Material,
	Mesh,
	OrthographicCamera,
	PCFShadowMap,
	PlaneGeometry,
	RGBAFormat,
	Scene,
	ShaderMaterial,
	Texture,
	UnsignedIntType,
	Vector2,
	WebGLRenderer,
	WebGLRenderTarget,
} from "three";

import { filmFragment, filmVertex } from "#shaders/film";

import type { TierSettings } from "./PerformanceManager";

/** Owns the WebGL context and the path from scene to final photographed image. */
export class Renderer {
	readonly webgl: WebGLRenderer;

	private readonly target: WebGLRenderTarget;
	private readonly film: ShaderMaterial;
	private readonly quad: Mesh;
	private readonly filmScene = new Scene();
	private readonly filmCamera = new OrthographicCamera(-1, 1, 1, -1, 0, 1);
	private readonly size = new Vector2();
	private ratio = 1;
	private scale = 1;
	private pendingScale: number | undefined;
	private readonly warmed = new Set<Texture>();

	constructor(
		canvas: HTMLCanvasElement,
		private readonly settings: TierSettings,
	) {
		this.webgl = new WebGLRenderer({ canvas, antialias: false, alpha: false, powerPreference: "high-performance", stencil: false, depth: false });
		this.webgl.setClearColor(0x1f4d5a, 1);
		this.webgl.shadowMap.enabled = settings.shadowSize > 0;
		this.webgl.shadowMap.type = PCFShadowMap;

		const depthTexture = new DepthTexture(4, 4, UnsignedIntType);
		this.target = new WebGLRenderTarget(4, 4, {
			type: HalfFloatType,
			format: RGBAFormat,
			minFilter: LinearFilter,
			magFilter: LinearFilter,
			samples: settings.samples,
			depthTexture,
			depthBuffer: true,
		});

		this.film = new ShaderMaterial({
			defines: { DOF_SAMPLES: settings.depthOfField },
			vertexShader: filmVertex,
			fragmentShader: filmFragment,
			uniforms: {
				tColor: { value: this.target.texture },
				tDepth: { value: depthTexture },
				uTexel: { value: new Vector2(1, 1) },
				uNear: { value: 0.1 },
				uFar: { value: 900 },
				uFocus: { value: 8 },
				uAperture: { value: 0 },
				uPose: { value: 0 },
				uExposure: { value: 1 },
				uGrain: { value: 0.03 },
				uAspect: { value: 1 },
			},
			depthTest: false,
			depthWrite: false,
			toneMapped: false,
		});
		this.quad = new Mesh(new PlaneGeometry(2, 2), this.film);
		this.quad.frustumCulled = false;
		this.filmScene.add(this.quad);
	}

	/**
	 * Matches the drawing buffers to the canvas.
	 * @param width CSS pixels.
	 * @param height CSS pixels.
	 */
	resize(width: number, height: number): void {
		this.size.set(width, height);
		const budget = Math.sqrt(this.settings.maxPixels / Math.max(1, width * height));
		this.ratio = Math.min(window.devicePixelRatio || 1, this.settings.maxPixelRatio, budget);
		this.applySize();
	}

	/**
	 * Changes the adaptive render scale.
	 * @param scale A multiplier on device pixel ratio.
	 */
	setScale(scale: number): void {
		this.pendingScale = scale;
	}

	/**
	 * Compiles shaders and uploads textures ahead of need, a little at a time, so that a set
	 * entering the frame for the first time costs nothing. Doing that work on first sight
	 * freezes the page for hundreds of milliseconds, right in the middle of a transition.
	 * @param scene The scene.
	 * @param camera The camera.
	 * @returns When everything currently in the scene is ready to draw.
	 */
	async prewarm(scene: Scene, camera: Camera): Promise<void> {
		const webgl = this.webgl;
		// Programs are keyed on their output, so compile against the same target the film renders to.
		webgl.setRenderTarget(this.target);
		await webgl.compileAsync(scene, camera);
		webgl.setRenderTarget(null);
		const textures = new Set<Texture>();
		scene.traverse((object) => {
			if (!(object instanceof Mesh)) return;
			const materials: Material[] = Array.isArray(object.material) ? object.material : [object.material];
			for (const material of materials) {
				for (const value of Object.values(material)) {
					if (value instanceof Texture && !this.warmed.has(value)) textures.add(value);
				}
			}
		});
		for (const texture of textures) {
			this.warmed.add(texture);
			webgl.initTexture(texture);
			await new Promise((resolve) => requestAnimationFrame(resolve));
		}
	}

	/**
	 * Draws one frame.
	 * @param scene The story scene.
	 * @param camera The story camera.
	 * @param pose The current pose number.
	 * @param focusDistance Distance of the plane of focus.
	 * @param aperture Depth-of-field strength.
	 */
	render(scene: Scene, camera: Camera, pose: number, focusDistance: number, aperture: number): void {
		// Resizing clears the canvas, so it must happen before a draw. Applied after one, the reader sees a blank frame.
		if (this.pendingScale !== undefined) {
			this.scale = this.pendingScale;
			this.pendingScale = undefined;
			this.applySize();
		}
		const uniforms = this.film.uniforms;
		if (uniforms["uPose"]) uniforms["uPose"].value = pose;
		if (uniforms["uFocus"]) uniforms["uFocus"].value = focusDistance;
		if (uniforms["uAperture"]) uniforms["uAperture"].value = aperture;
		const webgl = this.webgl;
		// Counts both passes of a frame together, so the debug numbers describe the whole frame.
		webgl.info.autoReset = false;
		webgl.info.reset();
		webgl.setRenderTarget(this.target);
		webgl.render(scene, camera);
		webgl.setRenderTarget(null);
		webgl.render(this.filmScene, this.filmCamera);
	}

	/** Releases GPU resources. */
	dispose(): void {
		this.target.dispose();
		this.film.dispose();
		this.webgl.dispose();
	}

	/** Applies the size and scale to the context, render target and film uniforms. */
	private applySize(): void {
		const pixelRatio = this.ratio * this.scale;
		this.webgl.setPixelRatio(pixelRatio);
		this.webgl.setSize(this.size.x, this.size.y, false);
		const width = Math.max(4, Math.floor(this.size.x * pixelRatio));
		const height = Math.max(4, Math.floor(this.size.y * pixelRatio));
		this.target.setSize(width, height);
		const uniforms = this.film.uniforms;
		uniforms["uTexel"]?.value.set(1 / width, 1 / height);
		if (uniforms["uAspect"]) uniforms["uAspect"].value = width / height;
	}
}
