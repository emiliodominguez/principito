import { SRGBColorSpace, type Texture, TextureLoader, type WebGLRenderer } from "three";
import { type GLTF, GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { KTX2Loader } from "three/addons/loaders/KTX2Loader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";

import type { Tier } from "./PerformanceManager";

/** Loads and caches models and painted layers for the current tier. Each file is requested once. */
export class AssetManager {
	private readonly gltf = new GLTFLoader();
	private readonly ktx2 = new KTX2Loader();
	private readonly textures = new TextureLoader();
	private readonly models = new Map<string, Promise<GLTF>>();
	private readonly images = new Map<string, Promise<Texture>>();
	private loaded = 0;
	private requested = 0;
	private readonly progressListeners = new Set<(share: number) => void>();

	constructor(
		renderer: WebGLRenderer,
		private readonly tier: Tier,
	) {
		this.ktx2.setTranscoderPath("/basis/");
		this.ktx2.detectSupport(renderer);
		this.gltf.setKTX2Loader(this.ktx2);
		MeshoptDecoder.useWorkers(2);
		this.gltf.setMeshoptDecoder(MeshoptDecoder);
	}

	/**
	 * Registers a loading-progress listener.
	 * @param listener Receives the finished share, 0 to 1.
	 */
	onProgress(listener: (share: number) => void): void {
		this.progressListeners.add(listener);
	}

	/**
	 * Loads a model for this tier.
	 * @param name Model name without extension.
	 * @returns The parsed glTF.
	 */
	model(name: string): Promise<GLTF> {
		const cached = this.models.get(name);
		if (cached) return cached;
		const request = this.track(this.gltf.loadAsync(`/models/${this.tier}/${name}.glb`));
		this.models.set(name, request);
		return request;
	}

	/**
	 * Loads a painted backdrop or paper layer for this tier.
	 * @param name Image name without extension.
	 * @returns The texture.
	 */
	painting(name: string): Promise<Texture> {
		const cached = this.images.get(name);
		if (cached) return cached;
		const request = this.track(this.textures.loadAsync(`/backgrounds/${this.tier}/${name}.webp`)).then((texture) => {
			texture.colorSpace = SRGBColorSpace;
			return texture;
		});
		this.images.set(name, request);
		return request;
	}

	/** Releases loaders and the transcoder worker. */
	dispose(): void {
		this.ktx2.dispose();
	}

	/**
	 * Counts a request toward the progress share.
	 * @param request The pending load.
	 * @returns The same request.
	 */
	private track<T>(request: Promise<T>): Promise<T> {
		this.requested++;
		void request.finally(() => {
			this.loaded++;
			for (const listener of this.progressListeners) listener(this.loaded / this.requested);
		});
		return request;
	}
}
