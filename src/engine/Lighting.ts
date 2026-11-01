import {
	Color,
	DirectionalLight,
	HemisphereLight,
	Mesh,
	MeshBasicMaterial,
	PMREMGenerator,
	PointLight,
	Scene,
	SphereGeometry,
	BackSide,
	CanvasTexture,
	type WebGLRenderer,
	Vector3,
} from "three";

import type { StageLook } from "#story/types";

import type { TierSettings } from "./PerformanceManager";

const KEY_DIRECTION = new Vector3(-0.56, 0.7, 0.62).normalize();

/** The studio: one big soft key, a sky fill and a small lamp for intimate scenes. */
export class Lighting {
	private readonly key = new DirectionalLight(0xffffff, 2);
	private readonly fill = new HemisphereLight(0xffffff, 0x234a52, 1);
	private readonly lamp = new PointLight(0xffc27a, 0, 7, 1.6);
	private readonly focus = new Vector3();

	constructor(scene: Scene, renderer: WebGLRenderer, settings: TierSettings) {
		scene.add(this.key, this.key.target, this.fill, this.lamp);
		if (settings.shadowSize > 0) {
			const light = this.key;
			light.castShadow = true;
			light.shadow.mapSize.set(settings.shadowSize, settings.shadowSize);
			light.shadow.camera.near = 0.5;
			light.shadow.camera.far = 40;
			light.shadow.bias = -0.0004;
			light.shadow.normalBias = 0.012;
			light.shadow.radius = settings.tier === "high" ? 7 : 4;
		}
		scene.environment = this.buildEnvironment(renderer);
		scene.environmentIntensity = 0.6;
	}

	/**
	 * Moves the shadow frustum to the action and applies a look.
	 * @param look The stage look.
	 * @param focus World point the camera is framing.
	 * @param reach Radius of what must receive shadows.
	 */
	update(look: StageLook, focus: Vector3, reach: number): void {
		const { key, fill, lamp } = this;
		key.color.setRGB(...look.keyColor);
		key.intensity = look.keyIntensity;
		fill.color.setRGB(...look.fillColor);
		fill.intensity = look.fillIntensity;
		lamp.intensity = look.glow * 1.5;
		// Snapped, or the shadow map slides under its texels every frame and edges shimmer as the camera travels.
		this.focus.set(Math.round(focus.x * 2) / 2, Math.round(focus.y * 2) / 2, Math.round(focus.z * 2) / 2);
		key.target.position.copy(this.focus);
		key.position.copy(this.focus).addScaledVector(KEY_DIRECTION, 18);
		key.target.updateMatrixWorld();
		const camera = key.shadow.camera;
		const size = Math.ceil(Math.min(14, Math.max(3, reach * 1.35)));
		if (camera.right !== size) {
			camera.left = -size;
			camera.right = size;
			camera.top = size;
			camera.bottom = -size;
			camera.updateProjectionMatrix();
		}
	}

	/**
	 * Places the small warm lamp.
	 * @param position World position.
	 */
	placeLamp(position: Vector3): void {
		this.lamp.position.copy(position);
	}

	/**
	 * Builds a soft studio reflection: a teal room with one large warm bounce card.
	 * Foil stars and the glass dome read mainly through this.
	 * @param renderer The WebGL renderer.
	 * @returns The filtered environment map.
	 */
	private buildEnvironment(renderer: WebGLRenderer) {
		const canvas = document.createElement("canvas");
		canvas.width = 256;
		canvas.height = 128;
		const context = canvas.getContext("2d");
		if (context) {
			const wall = context.createLinearGradient(0, 0, 0, 128);
			wall.addColorStop(0, "#bfcabf");
			wall.addColorStop(0.5, "#6f9a9c");
			wall.addColorStop(1, "#1f4d5a");
			context.fillStyle = wall;
			context.fillRect(0, 0, 256, 128);
			const card = context.createRadialGradient(70, 44, 2, 70, 44, 54);
			card.addColorStop(0, "#fff3d8");
			card.addColorStop(1, "rgb(255 235 200 / 0%)");
			context.fillStyle = card;
			context.fillRect(0, 0, 256, 128);
			const rim = context.createRadialGradient(200, 34, 2, 200, 34, 34);
			rim.addColorStop(0, "#ffd9a0");
			rim.addColorStop(1, "rgb(255 217 160 / 0%)");
			context.fillStyle = rim;
			context.fillRect(0, 0, 256, 128);
		}
		const texture = new CanvasTexture(canvas);
		const room = new Scene();
		const dome = new Mesh(
			new SphereGeometry(10, 24, 12),
			new MeshBasicMaterial({ map: texture, side: BackSide, color: new Color(1.6, 1.6, 1.6) }),
		);
		room.add(dome);
		const generator = new PMREMGenerator(renderer);
		const environment = generator.fromScene(room, 0.03).texture;
		generator.dispose();
		texture.dispose();
		return environment;
	}
}
