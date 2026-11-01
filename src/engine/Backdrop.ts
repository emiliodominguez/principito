import { BackSide, Mesh, MirroredRepeatWrapping, ShaderMaterial, SphereGeometry, type Texture, type Vector3 } from "three";

const vertexShader = /* glsl */ `
	varying vec3 vDirection;
	void main() {
		vDirection = position;
		vec4 clip = projectionMatrix * vec4(mat3(viewMatrix) * position, 1.0);
		gl_Position = clip.xyww;
	}
`;

const fragmentShader = /* glsl */ `
	precision highp float;
	varying vec3 vDirection;
	uniform sampler2D tNight;
	uniform sampler2D tDusk;
	uniform float uDusk;
	uniform float uExposure;
	uniform vec2 uDrift;
	uniform float uPan;

	const float PI = 3.14159265;

	float packAngle(float angle, float strength) {
		return tanh(angle * strength) / tanh(strength);
	}

	void main() {
		vec3 direction = normalize(vDirection);
		// Spreads the painting over the sky with more of it packed into the view than a plain wrap would,
		// so even the opening's narrow lens sees the deep corners. Its far edges meet behind the camera.
		float turn = atan(direction.x, -direction.z) - uPan;
		turn = atan(sin(turn), cos(turn));
		vec2 angles = vec2(turn / PI, asin(direction.y) / (PI * 0.5));
		vec2 packed = vec2(packAngle(angles.x, 3.4), packAngle(angles.y, 2.3));
		vec2 uv = packed * 0.5 + 0.5 + uDrift;
		vec3 color = mix(texture2D(tNight, uv).rgb, texture2D(tDusk, uv).rgb, uDusk);
		// The painting is only so sharp up close, so a second, finer sampling supplies paper tooth.
		float tooth = texture2D(tNight, uv * 6.3).g - texture2D(tNight, uv * 6.3 + 0.13).g;
		color *= 1.0 + tooth * 0.5;
		gl_FragColor = vec4(color * uExposure, 1.0);
	}
`;

/** The painted wall behind the set. Drawn at infinity and panned slightly as the camera travels. */
export class Backdrop {
	readonly mesh: Mesh;
	private readonly material: ShaderMaterial;

	constructor(night: Texture, dusk: Texture) {
		for (const texture of [night, dusk]) {
			texture.wrapS = MirroredRepeatWrapping;
			texture.wrapT = MirroredRepeatWrapping;
			texture.needsUpdate = true;
		}
		this.material = new ShaderMaterial({
			vertexShader,
			fragmentShader,
			uniforms: {
				tNight: { value: night },
				tDusk: { value: dusk },
				uDusk: { value: 0 },
				uExposure: { value: 1 },
				uDrift: { value: [0, 0] },
				uPan: { value: 0 },
			},
			side: BackSide,
			depthWrite: false,
			toneMapped: false,
		});
		this.mesh = new Mesh(new SphereGeometry(10, 32, 16), this.material);
		this.mesh.frustumCulled = false;
		this.mesh.renderOrder = -10;
	}

	/**
	 * Applies the lighting look and the camera's parallax against the wall.
	 * @param dusk Painting crossfade.
	 * @param exposure Brightness.
	 * @param camera Camera world position.
	 * @param heading Direction the lens faces, in radians around the set. The painting follows most of
	 * that turn, so the pale glow stays behind the action rather than being left at the wall's far end.
	 */
	update(dusk: number, exposure: number, camera: Vector3, heading: number): void {
		const uniforms = this.material.uniforms;
		if (uniforms["uDusk"]) uniforms["uDusk"].value = dusk;
		if (uniforms["uExposure"]) uniforms["uExposure"].value = exposure;
		if (uniforms["uDrift"]) uniforms["uDrift"].value = [camera.x * 0.0016, camera.y * 0.0024];
		if (uniforms["uPan"]) uniforms["uPan"].value = heading * 0.85;
	}

	/** Frees GPU resources. */
	dispose(): void {
		this.mesh.geometry.dispose();
		this.material.dispose();
	}
}
