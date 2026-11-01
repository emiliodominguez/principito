/**
 * The final image, photographed as if by a macro lens on a real stage: shallow focus,
 * film grain and a falloff at the frame's edge. Grain reads `uPose`, so it advances with the puppets.
 */

export const filmVertex = /* glsl */ `
	varying vec2 vUv;
	void main() {
		vUv = uv;
		gl_Position = vec4(position.xy, 0.0, 1.0);
	}
`;

export const filmFragment = /* glsl */ `
	precision highp float;
	varying vec2 vUv;
	uniform sampler2D tColor;
	uniform sampler2D tDepth;
	uniform vec2 uTexel;
	uniform float uNear;
	uniform float uFar;
	uniform float uFocus;
	uniform float uAperture;
	uniform float uPose;
	uniform float uExposure;
	uniform float uGrain;
	uniform float uAspect;

	const float MAX_BLUR = 0.011;

	float hash(vec2 p) {
		vec3 q = fract(vec3(p.xyx) * 0.1031);
		q += dot(q, q.yzx + 33.33);
		return fract((q.x + q.y) * q.z);
	}

	float viewDepth(vec2 uv) {
		float depth = texture2D(tDepth, uv).x;
		float ndc = depth * 2.0 - 1.0;
		return (2.0 * uNear * uFar) / (uFar + uNear - ndc * (uFar - uNear));
	}

	float blurRadius(float depth) {
		if (depth > uFar * 0.9) return 0.0;
		float distance = abs(depth - uFocus) / max(depth, 0.001);
		return clamp(distance * uAperture, 0.0, MAX_BLUR);
	}

	#if DOF_SAMPLES > 0
	// Scatter gathered: each sample asks whether its own blur disc reaches this pixel, so a soft
	// star spreads past its edge onto the sky, and bright foil blooms into round bokeh. A sample behind
	// a sharp subject cannot reach over it, which keeps the Prince's outline clean.
	vec3 lens(vec2 uv) {
		vec3 center = texture2D(tColor, uv).rgb;
		if (uAperture < 0.0001) return center;
		float depth = viewDepth(uv);
		float own = blurRadius(depth);
		vec3 sum = center;
		const float golden = 2.39996323;
		for (int i = 1; i <= DOF_SAMPLES; i++) {
			float f = float(i) / float(DOF_SAMPLES);
			float r = sqrt(f) * MAX_BLUR;
			float a = float(i) * golden;
			vec2 at = uv + vec2(cos(a) / uAspect, sin(a)) * r;
			float sampleDepth = viewDepth(at);
			float reach = sampleDepth < depth - 0.02 ? blurRadius(sampleDepth) : own;
			float w = smoothstep(r * 0.72, r, reach);
			vec3 color = texture2D(tColor, at).rgb;
			float bright = max(color.r, max(color.g, color.b));
			sum += mix(center, color * (1.0 + 0.7 * smoothstep(0.75, 1.3, bright)), w);
		}
		return sum / float(DOF_SAMPLES + 1);
	}
	#else
	vec3 lens(vec2 uv) {
		return texture2D(tColor, uv).rgb;
	}
	#endif

	// Khronos PBR Neutral: faithful below its shoulder, so painted colours stay as painted.
	vec3 neutral(vec3 color) {
		const float start = 0.8 - 0.04;
		const float desaturation = 0.15;
		float x = min(color.r, min(color.g, color.b));
		float offset = x < 0.08 ? x - 6.25 * x * x : 0.04;
		color -= offset;
		float peak = max(color.r, max(color.g, color.b));
		if (peak < start) return color;
		float d = 1.0 - start;
		float newPeak = 1.0 - d * d / (peak + d - start);
		color *= newPeak / peak;
		float g = 1.0 - 1.0 / (desaturation * (peak - newPeak) + 1.0);
		return mix(color, vec3(newPeak), g);
	}

	vec3 toSrgb(vec3 c) {
		return mix(12.92 * c, 1.055 * pow(max(c, vec3(0.0)), vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c));
	}

	void main() {
		vec3 color = lens(vUv) * uExposure;

		vec2 centered = vUv - 0.5;
		centered.x *= mix(1.0, uAspect, 0.35);
		float falloff = smoothstep(0.92, 0.28, length(centered));
		color *= mix(0.72, 1.0, falloff);

		color = neutral(color);
		// Soft lift in the shadows, as a photographed print never reaches pure black.
		color = color * 0.965 + vec3(0.012, 0.016, 0.018);
		color = toSrgb(color);

		float grain = hash(gl_FragCoord.xy + mod(uPose, 97.0) * 13.7) - 0.5;
		float luma = dot(color, vec3(0.3, 0.59, 0.11));
		color += grain * uGrain * (1.0 - luma * 0.6);
		gl_FragColor = vec4(color, 1.0);
	}
`;
