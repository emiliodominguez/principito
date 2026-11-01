import { CustomBlending, DoubleSide, OneFactor, OneMinusSrcAlphaFactor, ShaderMaterial } from "three";

const vertexShader = /* glsl */ `
	varying vec3 vNormal;
	varying vec3 vView;
	void main() {
		vec4 view = modelViewMatrix * vec4(position, 1.0);
		vNormal = normalMatrix * normal;
		vView = -view.xyz;
		gl_Position = projectionMatrix * view;
	}
`;

const fragmentShader = /* glsl */ `
	precision highp float;
	varying vec3 vNormal;
	varying vec3 vView;

	float box(vec2 p, vec2 center, vec2 extent, float soft) {
		vec2 d = abs(p - center) - extent;
		return smoothstep(soft, 0.0, max(d.x, d.y));
	}

	void main() {
		vec3 normal = normalize(vNormal) * (gl_FrontFacing ? 1.0 : -1.0);
		vec3 view = normalize(vView);
		float facing = clamp(dot(normal, view), 0.0, 1.0);
		float fresnel = 0.04 + 0.96 * pow(1.0 - facing, 5.0);
		vec3 reflected = reflect(-view, normal);

		// The studio seen in the curve of the jar: a big paned window on the key side, a thin strip opposite.
		vec2 r = reflected.xy;
		float window = box(r, vec2(-0.5, 0.26), vec2(0.17, 0.42), 0.035);
		window *= 1.0 - box(r, vec2(-0.5, 0.26), vec2(0.2, 0.012), 0.012);
		window *= 1.0 - box(r, vec2(-0.5, 0.26), vec2(0.012, 0.5), 0.012);
		float strip = box(r, vec2(0.72, 0.1), vec2(0.035, 0.5), 0.05);

		vec3 sky = mix(vec3(0.16, 0.3, 0.33), vec3(0.72, 0.8, 0.76), clamp(reflected.y * 0.5 + 0.5, 0.0, 1.0));
		vec3 light = vec3(1.0, 0.95, 0.86) * window * 0.26 + vec3(0.86, 0.95, 1.0) * strip * 0.13 + sky * fresnel * 0.8;
		// The inner wall reflects too, but through the glass it reads far dimmer.
		light *= gl_FrontFacing ? 1.0 : 0.3;

		// Clear in the middle; only the very edge, where the eye looks along the wall, gains a green body.
		float edge = pow(1.0 - facing, 3.5);
		float alpha = clamp(fresnel * 0.4 + edge * 0.24, 0.0, 0.62);
		gl_FragColor = vec4(light + vec3(0.42, 0.56, 0.5) * edge * 0.16, alpha);
	}
`;

/**
 * Thin blown glass. Glass mostly shows what it reflects, so this draws no surface colour at
 * all: the reflections are added on top of the scene, and only the grazing edge dims what
 * lies behind it. Reflections are painted from the studio's lights, which costs far less
 * than a refraction pass and keeps the crisp window shape that makes a bell jar read as glass.
 * @returns The material.
 */
export function createGlass(): ShaderMaterial {
	return new ShaderMaterial({
		vertexShader,
		fragmentShader,
		side: DoubleSide,
		transparent: true,
		depthWrite: false,
		toneMapped: false,
		blending: CustomBlending,
		blendSrc: OneFactor,
		blendDst: OneMinusSrcAlphaFactor,
	});
}
